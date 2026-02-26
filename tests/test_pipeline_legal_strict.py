from pathlib import Path

import pytest

from creative_automation_cli.exceptions import ComplianceViolationError
from creative_automation_cli.pipeline import RunConfig, run_pipeline


def test_pipeline_strict_legal_blocks_forbidden_message(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: legal_demo
message: "Get free money instantly"
target_region: US
target_audience: audience
products:
  - id: p1
    name: One
  - id: p2
    name: Two
""".strip(),
        encoding="utf-8",
    )

    legal_policy = tmp_path / "legal_policy.yaml"
    legal_policy.write_text(
        """
version: 1
default_action: block
checks:
  blocked_keywords: ["free money"]
  blocked_regex: []
locale_overrides: {}
""".strip(),
        encoding="utf-8",
    )

    config = RunConfig(
        brief_path=brief_file,
        assets_root=tmp_path / "assets",
        output_root=tmp_path / "output",
        provider_mode="mock",
        gemini_backend="developer",
        gemini_model="gemini-2.5-flash-image",
        locale=None,
        localize=False,
        dry_run=True,
        legal_policy_path=legal_policy,
        strict_legal=True,
    )

    with pytest.raises(ComplianceViolationError):
        run_pipeline(config)
