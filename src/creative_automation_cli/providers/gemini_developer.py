from __future__ import annotations

import io
import os

from PIL import Image

from .base import ImageProvider


class GeminiDeveloperProvider(ImageProvider):
    def __init__(self, model: str, api_key_env: str = "GEMINI_API_KEY"):
        self.model = model
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"Missing API key environment variable: {api_key_env}")

        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Developer Gemini mode requires optional dependency: google-genai") from exc

        self._client = genai.Client(api_key=self.api_key)

    def generate_base_hero(self, prompt: str, size: tuple[int, int], negative_prompt: str | None = None) -> Image.Image:
        merged_prompt = prompt
        if negative_prompt:
            merged_prompt += f"\nAvoid: {negative_prompt}"
        merged_prompt += f"\nRequired output size target: {size[0]}x{size[1]}"

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=[merged_prompt],
            )
        except Exception as exc:
            raise RuntimeError(
                f"Gemini Developer API call failed for model '{self.model}': {exc}. "
                "Check your GEMINI_API_KEY, network connectivity, and that the model name is correct."
            ) from exc

        parts = getattr(response, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data is not None:
                raw_bytes = getattr(inline_data, "data", None)
                if raw_bytes:
                    return Image.open(io.BytesIO(raw_bytes)).convert("RGB")

                if hasattr(part, "as_image"):
                    sdk_image = part.as_image()
                    if hasattr(sdk_image, "convert"):
                        return sdk_image.convert("RGB")
                    if hasattr(sdk_image, "_pil_image") and hasattr(sdk_image._pil_image, "convert"):
                        return sdk_image._pil_image.convert("RGB")

        raise RuntimeError(
            f"Gemini response from model '{self.model}' did not contain image data. "
            "Use an image-capable model such as gemini-2.5-flash-image."
        )
