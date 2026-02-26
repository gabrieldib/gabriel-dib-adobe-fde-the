from pathlib import Path

from PIL import Image

from creative_automation_cli.compliance.brand import evaluate_brand_compliance
from creative_automation_cli.compliance.policy import load_brand_policy


def test_load_brand_policy_yaml(tmp_path: Path) -> None:
    policy_path = tmp_path / "brand_policy.yaml"
    policy_path.write_text(
        """
policy_version: "1.0"
brand_name: "Test"
logo:
  required: true
  expected_filenames: ["logo.png"]
  safe_corner: top-right
  max_relative_width: 0.22
colors:
  required_palette: ["#FFFFFF"]
  tolerance: 20
  min_coverage: 0.01
imagery:
  required_keywords: ["premium"]
  avoid_keywords: ["watermark"]
typography:
  primary_typeface: "arial.ttf"
  fallback_typefaces: ["segoeui.ttf"]
""".strip(),
        encoding="utf-8",
    )

    policy = load_brand_policy(policy_path)
    assert policy.logo.required is True
    assert policy.logo.expected_filenames == ["logo.png"]
    assert policy.typography.primary_typeface == "arial.ttf"


def test_compliance_flags_missing_required_logo() -> None:
    policy = load_brand_policy(Path("config/brand_policy.yaml"))
    image = Image.new("RGB", (200, 200), (255, 255, 255))

    result = evaluate_brand_compliance(
        final_image=image,
        policy=policy,
        logo_path=None,
        prompt_text="premium studio product image",
    )

    assert result.passed is False
    assert any("logo" in violation.lower() for violation in result.violations)
