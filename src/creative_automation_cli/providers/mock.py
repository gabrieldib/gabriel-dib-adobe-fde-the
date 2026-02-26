from __future__ import annotations

import hashlib

from PIL import Image, ImageDraw, ImageFont

from .base import ImageProvider


class MockImageProvider(ImageProvider):
    def generate_base_hero(self, prompt: str, size: tuple[int, int], negative_prompt: str | None = None) -> Image.Image:
        width, height = size
        digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        color_a = tuple(int(digest[i : i + 2], 16) for i in (0, 2, 4))
        color_b = tuple(int(digest[i : i + 2], 16) for i in (6, 8, 10))

        image = Image.new("RGB", (width, height), color_a)
        draw = ImageDraw.Draw(image)

        for y in range(height):
            blend = y / max(height - 1, 1)
            r = int(color_a[0] * (1 - blend) + color_b[0] * blend)
            g = int(color_a[1] * (1 - blend) + color_b[1] * blend)
            b = int(color_a[2] * (1 - blend) + color_b[2] * blend)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        try:
            font = ImageFont.truetype("arial.ttf", 30)
        except OSError:
            font = ImageFont.load_default()

        label = "MOCK HERO"
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_w = text_bbox[2] - text_bbox[0]
        text_h = text_bbox[3] - text_bbox[1]

        draw.rounded_rectangle(
            [(20, 20), (20 + text_w + 24, 20 + text_h + 16)],
            radius=12,
            fill=(0, 0, 0),
        )
        draw.text((32, 28), label, fill=(255, 255, 255), font=font)
        return image
