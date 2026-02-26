from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Bundled font files shipped in assets/fonts/ — resolved relative to this module file
_BUNDLED_FONTS_DIR = Path(__file__).resolve().parents[3] / "assets" / "fonts"

MIN_MESSAGE_FONT_SIZE_PX = 24
MAX_FONT_BOX_HEIGHT_RATIO = 0.45
LINE_SPACING_RATIO = 0.35


def _normalize_hex_color(color: str) -> tuple[int, int, int]:
    value = color.strip().lstrip("#")
    if len(value) != 6:
        return 255, 255, 255
    return int(value[0:2], 16), int(value[2:4], 16), int(value[4:6], 16)


def _apply_case(message: str, message_case: str) -> str:
    if message_case == "all-upper":
        return message.upper()
    if message_case == "all-lower":
        return message.lower()
    return message


def _ordered_font_candidates(preferred_fonts: list[str] | None) -> list[str]:
    defaults = ["arial.ttf", "segoeui.ttf"]
    if not preferred_fonts:
        return defaults

    seen: set[str] = set()
    ordered: list[str] = []
    for name in [*preferred_fonts, *defaults]:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _pick_font(
    font_size: int,
    preferred_fonts: list[str] | None = None,
) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Resolve the best available font for *font_size*.

    Search order:
    1. Bundled fonts in ``assets/fonts/`` (ships with the repo — no system install required).
    2. System font lookup via Pillow.
    3. Pillow built-in bitmap default.
    """
    for font_name in _ordered_font_candidates(preferred_fonts):
        bundled_path = _BUNDLED_FONTS_DIR / font_name
        if bundled_path.exists():
            try:
                return ImageFont.truetype(str(bundled_path), font_size)
            except OSError:
                pass
        try:
            return ImageFont.truetype(font_name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
) -> list[str]:
    if max_width <= 0:
        return [text] if text else []

    def split_oversized_word(word: str) -> list[str]:
        chunks: list[str] = []
        current = ""
        for character in word:
            candidate = current + character
            candidate_bbox = draw.textbbox((0, 0), candidate, font=font)
            candidate_width = candidate_bbox[2] - candidate_bbox[0]
            if candidate_width <= max_width or not current:
                current = candidate
            else:
                chunks.append(current)
                current = character
        if current:
            chunks.append(current)
        return chunks

    words = text.split()
    lines: list[str] = []
    current_line: list[str] = []

    for word in words:
        candidate = " ".join([*current_line, word]).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current_line.append(word)
        elif not current_line:
            lines.extend(split_oversized_word(word))
        else:
            lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))
    return lines


def _line_height(draw: ImageDraw.ImageDraw, font: ImageFont.FreeTypeFont | ImageFont.ImageFont) -> int:
    bbox = draw.textbbox((0, 0), "Ag", font=font)
    return int(bbox[3] - bbox[1])


def _wrapped_text_total_height(line_height: int, line_count: int) -> int:
    if line_count <= 0:
        return 0
    return line_height * line_count + max(0, line_count - 1) * int(line_height * LINE_SPACING_RATIO)


def _choose_fitting_font(
    draw: ImageDraw.ImageDraw,
    message: str,
    preferred_fonts: list[str] | None,
    max_text_width: int,
    max_text_height: int,
) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, list[str], int]:
    max_candidate = max(MIN_MESSAGE_FONT_SIZE_PX, int(max_text_height * MAX_FONT_BOX_HEIGHT_RATIO))

    best_font = _pick_font(MIN_MESSAGE_FONT_SIZE_PX, preferred_fonts)
    best_lines = _wrap_text(draw, message, best_font, max_text_width)
    best_line_height = _line_height(draw, best_font)

    low = MIN_MESSAGE_FONT_SIZE_PX
    high = max_candidate

    while low <= high:
        font_size = (low + high) // 2
        font = _pick_font(font_size, preferred_fonts)
        lines = _wrap_text(draw, message, font, max_text_width)
        line_height = _line_height(draw, font)
        total_height = _wrapped_text_total_height(line_height, len(lines))

        if total_height <= max_text_height:
            best_font = font
            best_lines = lines
            best_line_height = line_height
            low = font_size + 1
        else:
            high = font_size - 1

    return best_font, best_lines, best_line_height


def overlay_campaign_message(
    image: Image.Image,
    message: str,
    preferred_fonts: list[str] | None = None,
    message_case: str = "normal",
    text_color: str = "#FFFFFF",
) -> Image.Image:
    composed = image.convert("RGBA")
    width, height = composed.size

    side_padding = int(width * 0.05)
    bottom_padding = int(height * 0.04)
    container_height = int(height * 0.28)
    x1 = side_padding
    x2 = width - side_padding
    y2 = height - bottom_padding
    y1 = y2 - container_height

    container_width = x2 - x1
    container_height_px = y2 - y1
    blurred_region = composed.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(radius=15))
    mask = Image.new("L", (container_width, container_height_px), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.rounded_rectangle([(0, 0), (container_width, container_height_px)], radius=24, fill=255)
    original_region = composed.crop((x1, y1, x2, y2))
    original_region.paste(blurred_region, (0, 0), mask)
    composed.paste(original_region, (x1, y1))

    overlay = Image.new("RGBA", composed.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=24, fill=(176, 248, 255, 13))
    composed = Image.alpha_composite(composed, overlay)

    draw = ImageDraw.Draw(composed)
    text_padding_x = int((x2 - x1) * 0.08)
    text_padding_y = int(container_height * 0.18)
    text_area_x1 = x1 + text_padding_x
    text_area_x2 = x2 - text_padding_x
    text_area_width = text_area_x2 - text_area_x1
    max_text_width = text_area_width
    max_text_height = max(1, container_height - 2 * text_padding_y)

    rendered_message = _apply_case(message, message_case)
    font, lines, line_height = _choose_fitting_font(
        draw,
        rendered_message,
        preferred_fonts,
        max_text_width,
        max_text_height,
    )
    total_text_height = _wrapped_text_total_height(line_height, len(lines))
    current_y = y1 + text_padding_y + max(0, ((container_height - 2 * text_padding_y) - total_text_height) // 2)

    text_rgb = _normalize_hex_color(text_color)
    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=font)
        line_width = line_bbox[2] - line_bbox[0]
        text_x = text_area_x1 + max(0, (text_area_width - line_width) // 2)
        draw.text((text_x, current_y), line, fill=(*text_rgb, 240), font=font)
        current_y += int(line_height * (1 + LINE_SPACING_RATIO))

    return composed.convert("RGB")
