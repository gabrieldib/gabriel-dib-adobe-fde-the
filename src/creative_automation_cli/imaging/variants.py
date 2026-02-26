from __future__ import annotations

from PIL import Image, ImageOps

TARGET_VARIANTS: dict[str, tuple[int, int]] = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}


def create_variant(
    base_image: Image.Image,
    ratio_key: str,
    preserve_full_image: bool = False,
) -> Image.Image:
    target_size = TARGET_VARIANTS[ratio_key]

    if preserve_full_image:
        # No crop: resize to fit entire image inside target, pad remaining space
        return ImageOps.pad(
            base_image.convert("RGB"),
            target_size,
            method=Image.Resampling.LANCZOS,
            color=(18, 18, 18),   # neutral padding color
            centering=(0.5, 0.5),
        )

    # Existing behavior for generated images: center-crop to fill target
    return ImageOps.fit(
        base_image.convert("RGB"),
        target_size,
        method=Image.Resampling.LANCZOS,
        centering=(0.5, 0.5),
    )
