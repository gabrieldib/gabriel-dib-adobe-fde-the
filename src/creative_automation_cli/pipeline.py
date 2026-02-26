from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from creative_automation_cli.assets.resolver import ResolvedProductAssets, resolve_product_assets
from creative_automation_cli.brief_loader import load_and_validate_brief
from creative_automation_cli.compliance.brand import evaluate_brand_compliance
from creative_automation_cli.compliance.legal import evaluate_legal_text
from creative_automation_cli.compliance.legal_policy import LegalPolicy, load_legal_policy
from creative_automation_cli.compliance.policy import BrandPolicy, load_brand_policy
from creative_automation_cli.exceptions import ComplianceViolationError, ConfigurationError
from creative_automation_cli.imaging.logo_overlay import overlay_logo
from creative_automation_cli.imaging.text_overlay import overlay_campaign_message
from creative_automation_cli.imaging.variants import TARGET_VARIANTS, create_variant
from creative_automation_cli.localization import (
    MessageLocalizer,
    build_localizer,
    normalize_locale,
    resolve_output_locales,
)
from creative_automation_cli.models.brief import CampaignBrief
from creative_automation_cli.output.manifest import CampaignManifest, ProductManifestEntry, utc_now_iso
from creative_automation_cli.output.metrics import RunMetrics, Timer
from creative_automation_cli.output.writer import save_image, write_json
from creative_automation_cli.prompts.builder import build_generation_prompt
from creative_automation_cli.providers.base import ImageProvider
from creative_automation_cli.providers.factory import create_provider
from creative_automation_cli.storage import GeneratedImageStore, S3Mirror

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _ProductResult:
    """Counters and manifest entry produced by processing one product."""

    entry: ProductManifestEntry
    assets_reused: int
    assets_generated: int
    variants_produced: int
    legal_checked: int
    legal_flagged: int
    legal_blocked: int
    compliance_passed: int
    compliance_failed: int


@dataclass(slots=True)
class RunConfig:
    brief_path: Path
    assets_root: Path
    output_root: Path
    provider_mode: str
    gemini_backend: str
    gemini_model: str
    locale: str | None
    localize: bool = False
    dry_run: bool = False
    brand_policy_path: Path | None = None
    strict_brand: bool = False
    legal_policy_path: Path | None = None
    strict_legal: bool = False
    generated_image_mode: str = "new"
    generated_image_id: str | None = None
    storage_root: Path = Path("./storage")


def _default_brand_policy_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "brand_policy.yaml"


def _resolve_brand_policy(path: Path | None) -> tuple[BrandPolicy | None, Path | None]:
    policy_path = path or _default_brand_policy_path()
    if policy_path.exists():
        return load_brand_policy(policy_path), policy_path
    return None, None


def _default_legal_policy_path() -> Path:
    return Path(__file__).resolve().parents[2] / "config" / "legal_policy.yaml"


def _resolve_legal_policy(path: Path | None) -> tuple[LegalPolicy | None, Path | None]:
    policy_path = path or _default_legal_policy_path()
    if policy_path.exists():
        return load_legal_policy(policy_path), policy_path
    return None, None


def _target_size_from_product(product_size: tuple[int, int], ratio_key: str) -> tuple[int, int]:
    product_width, product_height = product_size

    if ratio_key == "1x1":
        side = max(product_width, product_height)
        return side, side

    if ratio_key == "9x16":
        width = product_width
        height = max(1, round(width * 16 / 9))
        return width, height

    if ratio_key == "16x9":
        height = product_height
        width = max(1, round(height * 16 / 9))
        return width, height

    raise ValueError(f"Unsupported ratio key: {ratio_key}")


def _cover_and_center_crop(image: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    target_width, target_height = target_size
    src_width, src_height = image.size

    scale = max(target_width / src_width, target_height / src_height)
    resized_width = max(target_width, round(src_width * scale))
    resized_height = max(target_height, round(src_height * scale))

    resized = image.resize((resized_width, resized_height), Image.Resampling.LANCZOS)
    left = (resized_width - target_width) // 2
    top = (resized_height - target_height) // 2
    return resized.crop((left, top, left + target_width, top + target_height))


def _compose_reused_variant(resolved: ResolvedProductAssets, ratio_key: str) -> Image.Image:
    if resolved.hero_path is None:
        raise ValueError("Expected hero_path for reused asset composition")

    product_rgba = Image.open(resolved.hero_path).convert("RGBA")
    target_size = _target_size_from_product(product_rgba.size, ratio_key)

    if resolved.background_path and resolved.background_path.exists():
        background_rgb = Image.open(resolved.background_path).convert("RGB")
        background_rgba = _cover_and_center_crop(background_rgb, target_size).convert("RGBA")
    else:
        background_rgba = Image.new("RGBA", target_size, (255, 255, 255, 255))

    canvas = background_rgba.copy()
    product_x = (target_size[0] - product_rgba.width) // 2
    product_y = (target_size[1] - product_rgba.height) // 2
    canvas.alpha_composite(product_rgba, dest=(product_x, product_y))
    return canvas.convert("RGB")

def _load_reused_or_generate_base(
    resolved: ResolvedProductAssets,
    provider,
    prompt: str,
    negative_prompt: str | None,
    store: GeneratedImageStore,
    generated_image_mode: str,
    generated_image_id: str | None,
    dry_run: bool,
) -> tuple[Image.Image, str]:
    if resolved.hero_path and resolved.hero_path.exists():
        logger.info("Reusing hero image for product %s", resolved.product.id)
        return _compose_reused_variant(resolved, "1x1"), "reused"

    if generated_image_mode == "last":
        last_result = store.load_last_for_product(resolved.product.id)
        if last_result is not None:
            image_id, image = last_result
            logger.info("Using last generated image %s for product %s", image_id, resolved.product.id)
            return image, "generated_last"
        logger.info("No previous generated image found for product %s. Generating new one.", resolved.product.id)

    if generated_image_mode == "id":
        if not generated_image_id:
            raise ValueError("--generated-image-id is required when --generated-image-mode id")
        by_id = store.load_by_id(generated_image_id)
        if by_id is None:
            raise ValueError(f"Generated image id not found in storage: {generated_image_id}")
        image_id, image = by_id
        logger.info("Using generated image id %s for product %s", image_id, resolved.product.id)
        return image, "generated_id"

    logger.info("Generating hero image for product %s", resolved.product.id)
    generated = provider.generate_base_hero(prompt=prompt, size=(1536, 1536), negative_prompt=negative_prompt)
    if not dry_run:
        image_id, image_path = store.save_new(resolved.product.id, generated)
        logger.info("Stored generated image %s at %s", image_id, image_path)
    return generated, "generated_new"


def _process_product(
    resolved: ResolvedProductAssets,
    brief: CampaignBrief,
    provider: ImageProvider,
    localizer: MessageLocalizer,
    brand_policy: BrandPolicy | None,
    legal_policy: LegalPolicy | None,
    locales_to_render: list[str],
    config: RunConfig,
    generated_store: GeneratedImageStore,
    s3_mirror: S3Mirror | None = None,
) -> _ProductResult:
    """Process a single product: generate/reuse base hero, 
    create ratio variants, apply overlays and compliance checks."""
    prompt = build_generation_prompt(brief, resolved)
    base_image = None
    base_source = resolved.hero_source

    if resolved.hero_source != "reused":
        base_image, base_source = _load_reused_or_generate_base(
            resolved,
            provider,
            prompt,
            brief.negative_prompt,
            generated_store,
            config.generated_image_mode,
            config.generated_image_id,
            config.dry_run,
        )

    entry = ProductManifestEntry(
        product_id=resolved.product.id,
        product_name=resolved.product.name,
        hero_source=base_source,
    )

    legal_checked = 0
    legal_flagged = 0
    legal_blocked = 0
    compliance_passed = 0
    compliance_failed = 0

    if legal_policy is not None:
        prompt_legal = evaluate_legal_text(
            text=prompt,
            locale="en",
            policy=legal_policy,
            strict_legal=config.strict_legal,
        )
        entry.legal["prompt"] = prompt_legal.to_dict()
        legal_checked += 1
        if prompt_legal.flagged:
            legal_flagged += 1
        if prompt_legal.should_block:
            legal_blocked += 1
            raise ComplianceViolationError(
                f"Legal compliance failed for product={resolved.product.id} prompt: "
                + "; ".join(prompt_legal.violations),
                violations=prompt_legal.violations,
            )

    assets_reused = 1 if base_source in {"reused", "generated_last", "generated_id"} else 0
    variants_produced = 0

    for ratio_key in TARGET_VARIANTS:
        if resolved.hero_source == "reused":
            ratio_variant = _compose_reused_variant(resolved, ratio_key)
        else:
            if base_image is None:
                raise ValueError("Expected generated base image for non-reused asset")
            ratio_variant = create_variant(base_image, ratio_key)

        preferred_fonts = None
        message_case = "normal"
        message_color = "#FFFFFF"
        if brand_policy is not None:
            preferred_fonts = [
                brand_policy.typography.primary_typeface,
                *brand_policy.typography.fallback_typefaces,
            ]
            message_case = brand_policy.typography.case
            message_color = brand_policy.typography.color

        for locale_code in locales_to_render:
            localized_message = brief.message if locale_code == "en" else localizer.translate(brief.message, locale_code)

            if legal_policy is not None:
                message_legal = evaluate_legal_text(
                    text=localized_message,
                    locale=locale_code,
                    policy=legal_policy,
                    strict_legal=config.strict_legal,
                )
                legal_key = "message_en" if locale_code == "en" else f"message_{normalize_locale(locale_code)}"
                entry.legal[legal_key] = message_legal.to_dict()
                legal_checked += 1
                if message_legal.flagged:
                    legal_flagged += 1
                if message_legal.should_block:
                    legal_blocked += 1
                    raise ComplianceViolationError(
                        f"Legal compliance failed for product={resolved.product.id} locale={locale_code} message: "
                        + "; ".join(message_legal.violations),
                        violations=message_legal.violations,
                    )

            localized_variant = overlay_campaign_message(
                ratio_variant,
                localized_message,
                preferred_fonts=preferred_fonts,
                message_case=message_case,
                text_color=message_color,
            )
            if resolved.logo_path:
                localized_variant = overlay_logo(localized_variant, resolved.logo_path)

            locale_suffix = "" if locale_code == "en" else f"_{normalize_locale(locale_code)}"
            output_path = config.output_root / brief.campaign_id / resolved.product.id / ratio_key / f"final{locale_suffix}.png"

            if brand_policy is not None:
                compliance = evaluate_brand_compliance(
                    final_image=localized_variant,
                    policy=brand_policy,
                    logo_path=resolved.logo_path,
                    prompt_text=prompt,
                )
                compliance_key = ratio_key if locale_code == "en" else f"{ratio_key}_{normalize_locale(locale_code)}"
                entry.compliance[compliance_key] = compliance.to_dict()
                if compliance.passed:
                    compliance_passed += 1
                else:
                    compliance_failed += 1
                    violation_msg = (
                        "Brand compliance failed for "
                        f"product={resolved.product.id} ratio={ratio_key} locale={locale_code}: "
                        + "; ".join(compliance.violations)
                    )
                    if config.strict_brand:
                        raise ComplianceViolationError(violation_msg)
                    logger.warning(violation_msg)

            if not config.dry_run:
                save_image(localized_variant, output_path)
                if s3_mirror is not None:
                    s3_mirror.upload_output_file(output_path, config.output_root)

            variants_produced += 1
            output_key = ratio_key if locale_code == "en" else f"{ratio_key}_{normalize_locale(locale_code)}"
            entry.output_files[output_key] = str(output_path)

    return _ProductResult(
        entry=entry,
        assets_reused=assets_reused,
        assets_generated=1 - assets_reused,
        variants_produced=variants_produced,
        legal_checked=legal_checked,
        legal_flagged=legal_flagged,
        legal_blocked=legal_blocked,
        compliance_passed=compliance_passed,
        compliance_failed=compliance_failed,
    )


def run_pipeline(config: RunConfig) -> tuple[dict, dict]:
    timer = Timer()
    brief = load_and_validate_brief(config.brief_path)
    provider = create_provider(config.provider_mode, config.gemini_backend, config.gemini_model)
    localizer = build_localizer(config.localize, config.provider_mode, config.gemini_backend)
    s3_mirror = S3Mirror.from_env()
    generated_store = GeneratedImageStore(config.storage_root, s3_mirror=s3_mirror)
    resolved_assets = resolve_product_assets(config.assets_root, brief)
    brand_policy, policy_path = _resolve_brand_policy(config.brand_policy_path)
    legal_policy, legal_policy_path = _resolve_legal_policy(config.legal_policy_path)
    locales_to_render = resolve_output_locales(config.localize, brief.locals, config.locale)

    manifest = CampaignManifest(
        campaign_id=brief.campaign_id,
        target_region=brief.target_region,
        target_audience=brief.target_audience,
        message=brief.message,
        provider=config.provider_mode,
        dry_run=config.dry_run,
        brand_policy_path=str(policy_path) if policy_path else None,
        strict_brand=config.strict_brand,
        legal_policy_path=str(legal_policy_path) if legal_policy_path else None,
        strict_legal=config.strict_legal,
        started_at=utc_now_iso(),
    )
    manifest.locales_processed = locales_to_render
    metrics = RunMetrics()
    compliance_passed = 0
    compliance_failed = 0
    legal_checked = 0
    legal_flagged = 0
    legal_blocked = 0

    logger.info("Campaign %s started", brief.campaign_id)
    if config.locale:
        logger.info("Additional locale requested via --locale: %s", config.locale)

    for resolved in resolved_assets:
        result = _process_product(
            resolved=resolved,
            brief=brief,
            provider=provider,
            localizer=localizer,
            brand_policy=brand_policy,
            legal_policy=legal_policy,
            locales_to_render=locales_to_render,
            config=config,
            generated_store=generated_store,
            s3_mirror=s3_mirror,
        )
        manifest.products.append(result.entry)
        metrics.total_products_processed += 1
        metrics.assets_reused += result.assets_reused
        metrics.assets_generated += result.assets_generated
        metrics.total_variants_produced += result.variants_produced
        compliance_passed += result.compliance_passed
        compliance_failed += result.compliance_failed
        legal_checked += result.legal_checked
        legal_flagged += result.legal_flagged
        legal_blocked += result.legal_blocked

    metrics.execution_time_seconds = round(timer.elapsed(), 3)
    manifest.finished_at = utc_now_iso()
    if brand_policy is not None:
        manifest.brand_compliance_summary = {
            "variants_checked": compliance_passed + compliance_failed,
            "variants_passed": compliance_passed,
            "variants_failed": compliance_failed,
        }
    if legal_policy is not None:
        manifest.legal_compliance_summary = {
            "checks_executed": legal_checked,
            "checks_flagged": legal_flagged,
            "checks_blocked": legal_blocked,
        }

    manifest_path = config.output_root / brief.campaign_id / "manifest.json"
    metrics_path = config.output_root / brief.campaign_id / "metrics.json"
    write_json(manifest.to_dict(), manifest_path)
    write_json(metrics.to_dict(), metrics_path)
    if s3_mirror is not None:
        s3_mirror.upload_output_file(manifest_path, config.output_root)
        s3_mirror.upload_output_file(metrics_path, config.output_root)

    logger.info("Campaign %s completed", brief.campaign_id)
    return manifest.to_dict(), metrics.to_dict()


def run_legal_validation_only(config: RunConfig) -> dict:
    brief = load_and_validate_brief(config.brief_path)
    legal_policy, legal_policy_path = _resolve_legal_policy(config.legal_policy_path)
    if legal_policy is None:
        raise ConfigurationError(
            "No legal policy found. Provide --legal-policy or add config/legal_policy.yaml before using --validate-legal-only."
        )

    localizer = build_localizer(config.localize, config.provider_mode, config.gemini_backend)
    locales_to_render = resolve_output_locales(config.localize, brief.locals, config.locale)

    checks_executed = 0
    checks_flagged = 0
    checks_blocked = 0
    products: list[dict] = []

    for product in brief.products:
        resolved = ResolvedProductAssets(
            product=product,
            product_dir=Path("."),
            hero_path=None,
            logo_path=None,
            background_path=None,
            hero_source="generated",
        )
        product_prompt = build_generation_prompt(brief, resolved)
        prompt_result = evaluate_legal_text(
            text=product_prompt,
            locale="en",
            policy=legal_policy,
            strict_legal=config.strict_legal,
        )
        checks_executed += 1
        if prompt_result.flagged:
            checks_flagged += 1
        if prompt_result.should_block:
            checks_blocked += 1

        message_results: dict[str, dict] = {}
        for locale_code in locales_to_render:
            localized_message = brief.message if locale_code == "en" else localizer.translate(brief.message, locale_code)
            message_result = evaluate_legal_text(
                text=localized_message,
                locale=locale_code,
                policy=legal_policy,
                strict_legal=config.strict_legal,
            )
            checks_executed += 1
            if message_result.flagged:
                checks_flagged += 1
            if message_result.should_block:
                checks_blocked += 1
            message_results[locale_code] = message_result.to_dict()

        products.append(
            {
                "product_id": resolved.product.id,
                "prompt": prompt_result.to_dict(),
                "messages": message_results,
            }
        )

    summary = {
        "campaign_id": brief.campaign_id,
        "legal_policy_path": str(legal_policy_path),
        "strict_legal": config.strict_legal,
        "locales_checked": locales_to_render,
        "checks_executed": checks_executed,
        "checks_flagged": checks_flagged,
        "checks_blocked": checks_blocked,
        "products": products,
    }

    if config.strict_legal and checks_blocked > 0:
        raise ComplianceViolationError(
            "Legal validation-only check failed in strict mode: "
            f"{checks_blocked} checks blocked out of {checks_executed}."
        )

    return summary
