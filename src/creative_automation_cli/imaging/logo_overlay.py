from __future__ import annotations

from pathlib import Path

from PIL import Image


def overlay_logo(image: Image.Image, logo_path: Path, max_relative_width: float = 0.18) -> Image.Image:
    if not logo_path.exists():
        return image

    base = image.convert("RGBA")
    logo = Image.open(logo_path).convert("RGBA")
    width, height = base.size

    max_logo_width = int(width * max_relative_width)
    if logo.width > max_logo_width:
        scale = max_logo_width / logo.width
        logo = logo.resize((int(logo.width * scale), int(logo.height * scale)), Image.Resampling.LANCZOS)

    safe_margin = int(width * 0.04)
    pos_x = width - logo.width - safe_margin
    pos_y = safe_margin
    base.alpha_composite(logo, dest=(pos_x, pos_y))
    return base.convert("RGB")
