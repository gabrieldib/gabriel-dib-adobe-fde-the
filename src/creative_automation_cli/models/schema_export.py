from __future__ import annotations

import json
from pathlib import Path

from .brief import CampaignBrief


def campaign_brief_json_schema() -> dict:
    return CampaignBrief.model_json_schema()


def write_campaign_schema(schema_path: Path) -> None:
    schema_path.parent.mkdir(parents=True, exist_ok=True)
    schema_path.write_text(json.dumps(campaign_brief_json_schema(), indent=2), encoding="utf-8")
