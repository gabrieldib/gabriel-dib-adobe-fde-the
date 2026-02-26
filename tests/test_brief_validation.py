from pathlib import Path

import pytest

from creative_automation_cli.brief_loader import BriefValidationError, load_and_validate_brief


def test_load_valid_yaml_brief(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: abc
message: hello
target_region: US
target_audience: gamers
products:
  - id: p1
    name: One
  - id: p2
    name: Two
""".strip(),
        encoding="utf-8",
    )
    brief = load_and_validate_brief(brief_file)
    assert brief.campaign_id == "abc"
    assert len(brief.products) == 2


def test_invalid_brief_includes_example(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text("campaign_id: only", encoding="utf-8")
    with pytest.raises(BriefValidationError) as exc:
        load_and_validate_brief(brief_file)
    assert "Minimal valid YAML example" in str(exc.value)
