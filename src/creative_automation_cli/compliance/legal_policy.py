from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

import yaml
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from pydantic import BaseModel, Field


class LegalChecksPolicy(BaseModel):
    blocked_keywords: list[str] = Field(default_factory=list)
    blocked_regex: list[str] = Field(default_factory=list)


class LegalPolicy(BaseModel):
    version: int = 1
    default_action: Literal["warn", "block"] = "warn"
    checks: LegalChecksPolicy = Field(default_factory=LegalChecksPolicy)
    locale_overrides: dict[str, LegalChecksPolicy] = Field(default_factory=dict)


def _load_json_or_yaml(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    content = path.read_text(encoding="utf-8")

    if suffix in {".yaml", ".yml"}:
        parsed = yaml.safe_load(content)
    elif suffix == ".json":
        parsed = json.loads(content)
    else:
        raise ValueError(f"Unsupported legal policy format: {path}")

    if not isinstance(parsed, dict):
        raise ValueError("Legal policy must be a top-level object/map")
    return parsed


def _default_schema_path() -> Path:
    return Path(__file__).resolve().parents[3] / "schemas" / "legal_policy.schema.json"


def load_legal_policy(policy_path: Path) -> LegalPolicy:
    if not policy_path.exists():
        raise FileNotFoundError(f"Legal policy file not found: {policy_path}")

    data = _load_json_or_yaml(policy_path)
    schema_path = _default_schema_path()

    if schema_path.exists():
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            validate(instance=data, schema=schema)
        except JsonSchemaValidationError as exc:
            raise ValueError(f"Legal policy schema validation failed: {exc.message}") from exc

    return LegalPolicy.model_validate(data)
