from __future__ import annotations

from abc import ABC, abstractmethod

from PIL import Image


class ImageProvider(ABC):
    @abstractmethod
    def generate_base_hero(self, prompt: str, size: tuple[int, int], negative_prompt: str | None = None) -> Image.Image:
        raise NotImplementedError
