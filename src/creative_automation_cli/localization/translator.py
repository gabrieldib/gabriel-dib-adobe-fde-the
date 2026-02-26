from __future__ import annotations

import os
from abc import ABC, abstractmethod


def normalize_locale(locale: str) -> str:
    return locale.strip().replace("-", "_").lower()


def is_english_locale(locale: str) -> bool:
    normalized = normalize_locale(locale)
    return normalized == "en" or normalized.startswith("en_")


def resolve_output_locales(enable_localization: bool, brief_locales: list[str], cli_locale: str | None) -> list[str]:
    locales = ["en"]
    if enable_localization:
        locales.extend(brief_locales)
        if cli_locale:
            locales.append(cli_locale)

    deduped: list[str] = []
    seen: set[str] = set()
    for locale in locales:
        normalized = normalize_locale(locale)
        canonical = "en" if is_english_locale(normalized) else normalized
        if canonical not in seen:
            seen.add(canonical)
            deduped.append(canonical)
    return deduped


class MessageLocalizer(ABC):
    @abstractmethod
    def translate(self, message: str, target_locale: str) -> str:
        raise NotImplementedError


class NoopLocalizer(MessageLocalizer):
    def translate(self, message: str, target_locale: str) -> str:
        return message


class MockLocalizer(MessageLocalizer):
    def translate(self, message: str, target_locale: str) -> str:
        return f"[{target_locale}] {message}"


class GeminiDeveloperLocalizer(MessageLocalizer):
    def __init__(self, model: str = "gemini-2.5-flash", api_key_env: str = "GEMINI_API_KEY"):
        self.api_key = os.getenv(api_key_env)
        if not self.api_key:
            raise ValueError(f"Missing API key environment variable: {api_key_env}")

        try:
            from google import genai  # type: ignore
        except ImportError as exc:
            raise RuntimeError("Localization with Gemini developer backend requires google-genai") from exc

        self._client = genai.Client(api_key=self.api_key)
        self.model = model

    def translate(self, message: str, target_locale: str) -> str:
        if is_english_locale(target_locale):
            return message

        prompt = (
            "Translate the following marketing campaign message from English into locale "
            f"'{target_locale}'. Keep intent and concise ad style. Return only the translated message.\n\n"
            f"Message: {message}"
        )
        response = self._client.models.generate_content(model=self.model, contents=[prompt])
        translated = getattr(response, "text", None)
        if translated and translated.strip():
            return translated.strip()

        parts = getattr(response, "parts", None) or []
        for part in parts:
            text = getattr(part, "text", None)
            if text and text.strip():
                return text.strip()
        return message


def build_localizer(enable_localization: bool, provider_mode: str, gemini_backend: str) -> MessageLocalizer:
    if not enable_localization:
        return NoopLocalizer()

    if provider_mode == "mock":
        return MockLocalizer()

    if provider_mode == "real" and gemini_backend == "developer":
        return GeminiDeveloperLocalizer()

    return NoopLocalizer()
