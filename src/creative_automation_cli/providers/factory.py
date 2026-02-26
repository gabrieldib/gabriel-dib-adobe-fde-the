from __future__ import annotations

from .base import ImageProvider
from .gemini_developer import GeminiDeveloperProvider
from .gemini_vertex import GeminiVertexProvider
from .mock import MockImageProvider


def create_provider(provider: str, gemini_backend: str, gemini_model: str) -> ImageProvider:
    if provider == "mock":
        return MockImageProvider()
    if provider != "real":
        raise ValueError(f"Unknown provider mode: {provider}")

    if gemini_backend == "developer":
        return GeminiDeveloperProvider(model=gemini_model)
    if gemini_backend == "vertex":
        return GeminiVertexProvider(model=gemini_model)

    raise ValueError(f"Unknown Gemini backend: {gemini_backend}")
