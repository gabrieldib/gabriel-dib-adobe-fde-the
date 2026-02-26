from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from pydantic import BaseModel, Field


class LogoPolicy(BaseModel):
    required: bool = False
    expected_filenames: list[str] = Field(default_factory=lambda: ["logo.png"])
    safe_corner: Literal["top-right", "top-left"] = "top-right"
    max_relative_width: float = Field(default=0.22, ge=0.05, le=0.6)


class ColorPolicy(BaseModel):
    required_palette: list[str] = Field(default_factory=list)
    tolerance: int = Field(default=35, ge=0, le=255)
    min_coverage: float = Field(default=0.01, ge=0.0, le=1.0)


class ImageryPolicy(BaseModel):
    required_keywords: list[str] = Field(default_factory=list)
    avoid_keywords: list[str] = Field(default_factory=list)


class TypographyPolicy(BaseModel):
    primary_typeface: str = "arial.ttf"
    fallback_typefaces: list[str] = Field(default_factory=lambda: ["segoeui.ttf"])
    case: Literal["normal", "all-upper", "all-lower"] = "normal"
    color: str = "#FFFFFF"


class BrandPolicy(BaseModel):
    policy_version: str = "1.0"
    brand_name: str = "default-brand"
    logo: LogoPolicy = Field(default_factory=LogoPolicy)
    colors: ColorPolicy = Field(default_factory=ColorPolicy)
    imagery: ImageryPolicy = Field(default_factory=ImageryPolicy)
    typography: TypographyPolicy = Field(default_factory=TypographyPolicy)


def _load_json_or_yaml(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        parsed = yaml.safe_load(content)
    elif suffix == ".json":
        parsed = json.loads(content)
    else:
        raise ValueError(f"Unsupported brand policy format: {path}")

    if not isinstance(parsed, dict):
        raise ValueError("Brand policy must be a top-level object/map")
    return parsed


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "brand_policy.schema.json"


def load_brand_policy(policy_path: Path) -> BrandPolicy:
    if not policy_path.exists():
        raise FileNotFoundError(f"Brand policy file not found: {policy_path}")

    data = _load_json_or_yaml(policy_path)
    schema_path = _default_schema_path()

    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            validate(instance=data, schema=schema)
        except JsonSchemaValidationError as exc:
            raise ValueError(f"Brand policy schema validation failed: {exc.message}") from exc

    return BrandPolicy.model_validate(data)
