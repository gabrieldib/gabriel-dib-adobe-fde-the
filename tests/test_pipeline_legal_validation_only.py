from pathlib import Path

from creative_automation_cli.pipeline import RunConfig, run_legal_validation_only


def test_legal_validation_only_returns_summary(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: legal_only_demo
message: "Get free money"
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
default_action: warn
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
        strict_legal=False,
    )

    summary = run_legal_validation_only(config)
    assert summary["campaign_id"] == "legal_only_demo"
    assert summary["checks_executed"] == 4
    assert summary["checks_flagged"] >= 2
    assert summary["checks_blocked"] == 0
