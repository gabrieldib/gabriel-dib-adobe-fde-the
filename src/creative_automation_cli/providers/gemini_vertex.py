from __future__ import annotations

import io
import os

from PIL import Image

from creative_automation_cli.exceptions import ProviderGenerationError

from .base import ImageProvider


class GeminiVertexProvider(ImageProvider):
    def __init__(self, model: str, project_env: str = "GOOGLE_CLOUD_PROJECT", location_env: str = "GOOGLE_CLOUD_LOCATION"):
        self.model = model
        self.project = os.getenv(project_env)
        self.location = os.getenv(location_env, "us-central1")
        if not self.project:
            raise ValueError(f"Missing environment variable: {project_env}")

        try:
            from google import genai  # type: ignore
            from google.genai import types  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Vertex mode requires optional dependency: google-genai") from exc

        self._genai = genai
        self._types = types
        self._client = genai.Client(vertexai=True, project=self.project, location=self.location)

    def generate_base_hero(self, prompt: str, size: tuple[int, int], negative_prompt: str | None = None) -> Image.Image:
        merged_prompt = prompt
        if negative_prompt:
            merged_prompt += f"\nAvoid: {negative_prompt}"
        merged_prompt += f"\nRequired output size target: {size[0]}x{size[1]}"

        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=merged_prompt,
                config=self._types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
            )
        except Exception as exc:
            raise ProviderGenerationError(
                f"Gemini Vertex API call failed for model '{self.model}' "
                f"(project={self.project}, location={self.location}): {exc}. "
                "Check your GOOGLE_CLOUD_PROJECT / GOOGLE_CLOUD_LOCATION env vars, ADC credentials, and model name."
            ) from exc

        if getattr(response, "candidates", None):
            for candidate in response.candidates:
                content = getattr(candidate, "content", None)
                parts = getattr(content, "parts", []) if content else []
                for part in parts:
                    inline_data = getattr(part, "inline_data", None)
                    if inline_data and getattr(inline_data, "data", None):
                        return Image.open(io.BytesIO(inline_data.data)).convert("RGB")
        raise ProviderGenerationError("Vertex Gemini response did not contain image data.")
