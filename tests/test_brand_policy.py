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
    """Logo violation only fires when policy explicitly sets required: true."""
    policy_path = Path("config/brand_policy.yaml")
    # Build an in-memory policy that opts-in to logo enforcement so the test
    # is not coupled to the on-disk config file (which may not require a logo).
    from creative_automation_cli.compliance.policy import (
        BrandPolicy,
        ColorPolicy,
        ImageryPolicy,
        LogoPolicy,
        TypographyPolicy,
    )

    policy = BrandPolicy(
        policy_version="1.0",
        brand_name="Test",
        logo=LogoPolicy(required=True, expected_filenames=["logo.png"], safe_corner="top-right", max_relative_width=0.22),
        colors=ColorPolicy(required_palette=[], tolerance=20, min_coverage=0.01),
        imagery=ImageryPolicy(required_keywords=[], avoid_keywords=[]),
        typography=TypographyPolicy(primary_typeface="arial.ttf", fallback_typefaces=[]),
    )
    image = Image.new("RGB", (200, 200), (255, 255, 255))

    result = evaluate_brand_compliance(
        final_image=image,
        policy=policy,
        logo_path=None,
        prompt_text="premium studio product image",
    )

    assert result.passed is False
    assert any("logo" in violation.lower() for violation in result.violations)


def test_compliance_passes_without_logo_when_not_required() -> None:
    """Missing logo is not a violation when required is not set."""
    from creative_automation_cli.compliance.policy import (
        BrandPolicy,
        ColorPolicy,
        ImageryPolicy,
        LogoPolicy,
        TypographyPolicy,
    )

    policy = BrandPolicy(
        policy_version="1.0",
        brand_name="Test",
        logo=LogoPolicy(safe_corner="top-right", max_relative_width=0.22),
        colors=ColorPolicy(required_palette=[], tolerance=20, min_coverage=0.01),
        imagery=ImageryPolicy(required_keywords=[], avoid_keywords=[]),
        typography=TypographyPolicy(primary_typeface="arial.ttf", fallback_typefaces=[]),
    )
    image = Image.new("RGB", (200, 200), (255, 255, 255))

    result = evaluate_brand_compliance(
        final_image=image,
        policy=policy,
        logo_path=None,
        prompt_text="premium studio product image",
    )

    assert result.passed is True
    assert not any("logo" in v.lower() for v in result.violations)
