from pathlib import Path

import pytest

from creative_automation_cli.exceptions import ComplianceViolationError
from creative_automation_cli.pipeline import RunConfig, run_pipeline


def test_pipeline_strict_brand_fails_when_logo_missing(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: strict_demo
message: headline
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

    policy_path = tmp_path / "brand_policy.yaml"
    policy_path.write_text(
        """
policy_version: "1.0"
brand_name: "Strict"
logo:
  required: true
  expected_filenames: ["logo.png"]
  safe_corner: top-right
  max_relative_width: 0.22
colors:
  required_palette: []
  tolerance: 35
  min_coverage: 0.01
imagery:
  required_keywords: []
  avoid_keywords: []
typography:
  primary_typeface: "arial.ttf"
  fallback_typefaces: ["segoeui.ttf"]
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
        dry_run=True,
        brand_policy_path=policy_path,
        strict_brand=True,
    )

    with pytest.raises(ComplianceViolationError):
        run_pipeline(config)
