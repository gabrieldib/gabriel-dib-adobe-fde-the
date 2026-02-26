from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .policy import BrandPolicy


@dataclass(slots=True)
class BrandCheckResult:
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "checks": self.checks,
            "warnings": self.warnings,
            "violations": self.violations,
        }


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    value = hex_color.strip().lstrip("#")
    if len(value) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _channel_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1]) + abs(a[2] - b[2])


def _as_rgb_tuple(pixel: tuple[int, ...] | float) -> tuple[int, int, int] | None:
    if not isinstance(pixel, tuple):
        return None
    if len(pixel) < 3:
        return None
    r, g, b = pixel[0], pixel[1], pixel[2]
    return int(r), int(g), int(b)


def _palette_coverage(image: Image.Image, target: tuple[int, int, int], tolerance: int) -> float:
    sample = image.convert("RGB").resize((120, 120), Image.Resampling.BILINEAR)
    colors = sample.getcolors(maxcolors=120 * 120)
    if not colors:
        return 0.0

    threshold = tolerance * 3
    total = 0
    matching = 0
    for count, pixel in colors:
        total += count
        rgb = _as_rgb_tuple(pixel)
        if rgb is None:
            continue
        if _channel_distance(rgb, target) <= threshold:
            matching += count
    if total == 0:
        return 0.0
    return matching / total


def evaluate_brand_compliance(
    final_image: Image.Image,
    policy: BrandPolicy,
    logo_path: Path | None,
    prompt_text: str,
) -> BrandCheckResult:
    checks: dict[str, bool] = {}
    warnings: list[str] = []
    violations: list[str] = []

    if policy.logo.required:
        has_logo = logo_path is not None and logo_path.exists()
        checks["logo_present"] = has_logo
        if not has_logo:
            violations.append("Required logo is missing.")
        else:
            if logo_path is None:
                raise ValueError("Expected logo path when logo presence check passes")
            if policy.logo.expected_filenames:
                expected_names = {name.lower() for name in policy.logo.expected_filenames}
                actual_name = logo_path.name.lower()
                matches_expected = actual_name in expected_names
                checks["logo_expected_filename"] = matches_expected
                if not matches_expected:
                    violations.append(
                        f"Logo filename '{logo_path.name}' is not in allowed set: {sorted(expected_names)}."
                    )
    else:
        checks["logo_present"] = logo_path is not None and logo_path.exists()

    if policy.colors.required_palette:
        palette_ok = True
        for hex_color in policy.colors.required_palette:
            rgb = _hex_to_rgb(hex_color)
            coverage = _palette_coverage(final_image, rgb, policy.colors.tolerance)
            color_key = f"color_{hex_color.lower()}"
            color_ok = coverage >= policy.colors.min_coverage
            checks[color_key] = color_ok
            if not color_ok:
                palette_ok = False
                warnings.append(
                    f"Palette color {hex_color} coverage {coverage:.3f} is below threshold {policy.colors.min_coverage:.3f}."
                )
        checks["palette_compliant"] = palette_ok

    prompt_lower = prompt_text.lower()
    if policy.imagery.required_keywords:
        required_ok = True
        for keyword in policy.imagery.required_keywords:
            present = keyword.lower() in prompt_lower
            checks[f"imagery_required_{keyword}"] = present
            if not present:
                required_ok = False
                warnings.append(f"Imagery keyword '{keyword}' not found in prompt.")
        checks["imagery_required_keywords"] = required_ok

    for keyword in policy.imagery.avoid_keywords:
        present = keyword.lower() in prompt_lower
        checks[f"imagery_avoid_{keyword}"] = not present
        if present:
            violations.append(f"Prohibited imagery keyword '{keyword}' present in prompt.")

    return BrandCheckResult(
        passed=len(violations) == 0,
        checks=checks,
        warnings=warnings,
        violations=violations,
    )
