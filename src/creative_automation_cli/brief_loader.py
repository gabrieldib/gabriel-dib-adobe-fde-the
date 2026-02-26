from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from .models.brief import CampaignBrief

MIN_VALID_EXAMPLE_YAML = """campaign_id: demo_campaign
message: "Primary campaign headline"
target_region: "US"
target_audience: "Young professionals"
products:
  - id: product_1
    name: "Product One"
  - id: product_2
    name: "Product Two"
"""


class BriefValidationError(ValueError):
    pass


def _parse_brief_file(brief_path: Path) -> dict[str, Any]:
    suffix = brief_path.suffix.lower()
    content = brief_path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        parsed = yaml.safe_load(content)
    elif suffix == ".json":
        parsed = json.loads(content)
    else:
        raise BriefValidationError(
            "Unsupported brief format. Use .yaml, .yml, or .json files.\n\n"
            f"Minimal valid YAML example:\n{MIN_VALID_EXAMPLE_YAML}"
        )

    if not isinstance(parsed, dict):
        raise BriefValidationError(
            "Brief root must be an object/map.\n\n"
            f"Minimal valid YAML example:\n{MIN_VALID_EXAMPLE_YAML}"
        )
    return parsed


def load_and_validate_brief(brief_path: Path) -> CampaignBrief:
    if not brief_path.exists():
        raise BriefValidationError(f"Brief file not found: {brief_path}")

    try:
        parsed = _parse_brief_file(brief_path)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise BriefValidationError(
            f"Unable to parse brief file: {exc}\n\n"
            f"Minimal valid YAML example:\n{MIN_VALID_EXAMPLE_YAML}"
        ) from exc

    try:
        return CampaignBrief.model_validate(parsed)
    except ValidationError as exc:
        errors = []
        for item in exc.errors():
            location = ".".join(str(part) for part in item["loc"])
            errors.append(f"- {location}: {item['msg']}")
        raise BriefValidationError(
            "Brief validation failed:\n"
            + "\n".join(errors)
            + "\n\nMinimal valid YAML example:\n"
            + MIN_VALID_EXAMPLE_YAML
        ) from exc
