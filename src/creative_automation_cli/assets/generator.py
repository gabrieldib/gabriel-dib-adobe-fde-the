from __future__ import annotations

import logging

from creative_automation_cli.assets.resolver import ResolvedProductAssets
from creative_automation_cli.models.brief import CampaignBrief
from creative_automation_cli.providers.base import ImageProvider
from creative_automation_cli.storage.generated_store import GeneratedImageStore

logger = logging.getLogger(__name__)

_PRODUCT_SIZE: tuple[int, int] = (1024, 1024)
_LOGO_SIZE: tuple[int, int] = (512, 512)
_BACKGROUND_SIZE: tuple[int, int] = (1920, 1080)


def _build_product_prompt(brief: CampaignBrief, resolved: ResolvedProductAssets) -> str:
    if resolved.product.prompt:
        return resolved.product.prompt
    style_keywords = (
        ", ".join(brief.visual_style.keywords)
        if brief.visual_style and brief.visual_style.keywords
        else ""
    )
    mood = brief.visual_style.mood if brief.visual_style and brief.visual_style.mood else ""
    parts = [
        f"Create a clean product packshot of '{resolved.product.name}' on a plain white background.",
        f"Target audience: {brief.target_audience}.",
        f"Target region: {brief.target_region}.",
        "Centered composition, professional product photography style.",
    ]
    if style_keywords:
        parts.append(f"Visual style: {style_keywords}.")
    if mood:
        parts.append(f"Mood: {mood}.")
    parts.append("No text overlays.")
    return " ".join(parts)


def _build_logo_prompt(brief: CampaignBrief, resolved: ResolvedProductAssets) -> str:
    return (
        f"Create a clean, minimal brand logo icon for '{resolved.product.name}'. "
        "Plain white background, no text, simple icon or symbol, "
        "professional graphic design, suitable for placement on advertising imagery."
    )


def _build_background_prompt(brief: CampaignBrief, resolved: ResolvedProductAssets) -> str:
    style_keywords = (
        ", ".join(brief.visual_style.keywords)
        if brief.visual_style and brief.visual_style.keywords
        else "premium, modern"
    )
    mood = brief.visual_style.mood if brief.visual_style and brief.visual_style.mood else ""
    parts = [
        f"Create a premium advertising background image for a '{resolved.product.name}' campaign.",
        f"Target audience: {brief.target_audience}.",
        f"Target region: {brief.target_region}.",
        f"Visual style: {style_keywords}.",
    ]
    if mood:
        parts.append(f"Mood: {mood}.")
    parts.append(
        "No products, no people, no text overlays. "
        "Full-bleed background suitable for advertising."
    )
    return " ".join(parts)


def ensure_product_assets(
    resolved: ResolvedProductAssets,
    brief: CampaignBrief,
    provider: ImageProvider,
    store: GeneratedImageStore,
    negative_prompt: str | None = None,
) -> tuple[ResolvedProductAssets, int, int]:
    """Generate and save any missing assets (product, logo, background).

    Each missing asset is generated via *provider*, saved flat into
    ``storage/generated/`` as ``{type}_{product_id}.png``, and mirrored to S3
    when a mirror is configured.  The returned :class:`ResolvedProductAssets`
    has its path fields updated to the newly created files so the rest of the
    pipeline picks them up without further changes.

    Returns:
        Tuple of (resolved, n_existing, n_generated) where each count tracks
        individual asset files (hero, logo, background).
    """
    product_id = resolved.product.id
    n_existing = 0
    n_generated = 0

    if resolved.hero_path is None:
        filename = f"product_{product_id}.png"
        logger.info("Generating product asset for %s → %s", product_id, filename)
        image = provider.generate_base_hero(
            prompt=_build_product_prompt(brief, resolved),
            size=_PRODUCT_SIZE,
            negative_prompt=negative_prompt,
        )
        dest = store.save_asset(filename, image)
        resolved.hero_path = dest
        n_generated += 1
        logger.info("Saved generated product asset: %s", dest)
    else:
        n_existing += 1

    if resolved.logo_path is None:
        filename = f"logo_{product_id}.png"
        logger.info("Generating logo asset for %s → %s", product_id, filename)
        image = provider.generate_base_hero(
            prompt=_build_logo_prompt(brief, resolved),
            size=_LOGO_SIZE,
            negative_prompt=None,
        )
        dest = store.save_asset(filename, image)
        resolved.logo_path = dest
        n_generated += 1
        logger.info("Saved generated logo asset: %s", dest)
    else:
        n_existing += 1

    if resolved.background_path is None:
        filename = f"background_{product_id}.png"
        logger.info("Generating background asset for %s → %s", product_id, filename)
        image = provider.generate_base_hero(
            prompt=_build_background_prompt(brief, resolved),
            size=_BACKGROUND_SIZE,
            negative_prompt=negative_prompt,
        )
        dest = store.save_asset(filename, image)
        resolved.background_path = dest
        n_generated += 1
        logger.info("Saved generated background asset: %s", dest)
    else:
        n_existing += 1

    return resolved, n_existing, n_generated
