from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path

from creative_automation_cli.brief_loader import BriefValidationError
from creative_automation_cli.pipeline import RunConfig, run_legal_validation_only, run_pipeline


def _strip_optional_quotes(value: str) -> str:
    trimmed = value.strip()
    if len(trimmed) >= 2 and ((trimmed[0] == '"' and trimmed[-1] == '"') or (trimmed[0] == "'" and trimmed[-1] == "'")):
        return trimmed[1:-1]
    return trimmed


def _load_env_file(env_path: Path) -> None:
    if not env_path.exists() or not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue

        value = _strip_optional_quotes(raw_value)
        os.environ.setdefault(key, value)


def _load_default_env_files() -> None:
    cwd_env = Path.cwd() / ".env"
    project_root_env = Path(__file__).resolve().parents[2] / ".env"

    _load_env_file(project_root_env)
    if cwd_env != project_root_env:
        _load_env_file(cwd_env)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Creative Automation CLI POC")
    parser.add_argument("--brief", required=True, help="Path to campaign brief (.yaml/.yml/.json)")
    parser.add_argument("--assets", required=False, default=None, help="Assets root folder")
    parser.add_argument("--output", required=False, default=None, help="Output root folder")
    parser.add_argument("--provider", choices=["mock", "real"], default="mock", help="Provider mode")
    parser.add_argument("--locale", default=None, help="Optional single locale to append to brief locals")
    parser.add_argument("--localize", action="store_true", help="Enable localization output using brief locals list")
    parser.add_argument("--dry-run", action="store_true", help="Plan actions and skip image file writes")
    parser.add_argument(
        "--gemini-backend",
        choices=["developer", "vertex"],
        default="developer",
        help="Gemini backend used when --provider real",
    )
    parser.add_argument(
        "--gemini-model",
        default=os.getenv("GEMINI_MODEL", "gemini-2.5-flash-image"),
        help="Gemini image model name",
    )
    parser.add_argument(
        "--brand-policy",
        default=None,
        help="Path to brand policy file (.yaml/.yml/.json). If omitted, config/brand_policy.yaml is used when present.",
    )
    parser.add_argument(
        "--strict-brand",
        action="store_true",
        help="Fail run when brand compliance violations are detected.",
    )
    parser.add_argument(
        "--legal-policy",
        default=None,
        help="Path to legal policy file (.yaml/.yml/.json). If omitted, config/legal_policy.yaml is used when present.",
    )
    parser.add_argument(
        "--strict-legal",
        action="store_true",
        help="Fail run when blocked legal terms/expressions are detected.",
    )
    parser.add_argument(
        "--validate-legal-only",
        action="store_true",
        help="Run legal policy checks only (no image generation or file output).",
    )
    parser.add_argument(
        "--storage-root",
        default="./storage",
        help="Local storage root for generated images.",
    )
    return parser.parse_args()


def main() -> None:
    _load_default_env_files()
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

    if not args.validate_legal_only and (not args.assets or not args.output):
        raise SystemExit("--assets and --output are required unless --validate-legal-only is used")

    assets_root = Path(args.assets) if args.assets else Path("./assets")
    output_root = Path(args.output) if args.output else Path("./output")

    config = RunConfig(
        brief_path=Path(args.brief),
        assets_root=assets_root,
        output_root=output_root,
        provider_mode=args.provider,
        gemini_backend=args.gemini_backend,
        gemini_model=args.gemini_model,
        locale=args.locale,
        localize=args.localize,
        dry_run=args.dry_run,
        brand_policy_path=Path(args.brand_policy) if args.brand_policy else None,
        strict_brand=args.strict_brand,
        legal_policy_path=Path(args.legal_policy) if args.legal_policy else None,
        strict_legal=args.strict_legal,
        storage_root=Path(args.storage_root),
    )

    try:
        if args.validate_legal_only:
            summary = run_legal_validation_only(config)
            print("Legal validation summary")
            print(f"- Campaign: {summary['campaign_id']}")
            print(f"- Checks executed: {summary['checks_executed']}")
            print(f"- Checks flagged: {summary['checks_flagged']}")
            print(f"- Checks blocked: {summary['checks_blocked']}")
            print("- Locales checked: " + ", ".join(summary["locales_checked"]))
            print(json.dumps(summary, indent=2))

            if summary.get("checks_flagged", 0) == 0:
                print("No legal violations found.")
            else:
                print(f"Legal violations found: {summary.get('checks_flagged', 0)}")

            warning_lines: list[str] = []
            for product in summary.get("products", []):
                product_id = product.get("product_id", "unknown")

                prompt = product.get("prompt", {})
                for warning in prompt.get("warnings", []):
                    warning_lines.append(f"- product={product_id} context=prompt: {warning}")

                for locale_code, message_result in product.get("messages", {}).items():
                    for warning in message_result.get("warnings", []):
                        warning_lines.append(
                            f"- product={product_id} context=message locale={locale_code}: {warning}"
                        )

            if warning_lines:
                print("Legal warnings by product")
                for line in warning_lines:
                    print(line)
            else:
                print("No legal warnings found.")
            return

        _, metrics = run_pipeline(config)
    except BriefValidationError as exc:
        raise SystemExit(f"Validation error:\n{exc}") from exc
    except Exception as exc:
        raise SystemExit(f"Pipeline failed: {exc}") from exc

    print("Run metrics")
    print(f"- Total products processed: {metrics['total_products_processed']}")
    print(f"- Assets reused: {metrics['assets_reused']}")
    print(f"- Assets generated: {metrics['assets_generated']}")
    print(f"- Total variants produced: {metrics['total_variants_produced']}")
    print(f"- Execution time (s): {metrics['execution_time_seconds']}")


if __name__ == "__main__":
    main()
