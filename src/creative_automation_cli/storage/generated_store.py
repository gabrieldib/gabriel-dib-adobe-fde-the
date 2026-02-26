from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image


class GeneratedImageStore:
    def __init__(self, storage_root: Path):
        self.storage_root = storage_root
        self.generated_root = storage_root / "generated"
        self.generated_root.mkdir(parents=True, exist_ok=True)

    def save_new(self, product_id: str, image: Image.Image) -> tuple[str, Path]:
        image_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
        product_dir = self.generated_root / product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        image_path = product_dir / f"{image_id}.png"
        image.save(image_path, format="PNG")
        return image_id, image_path

    def load_last_for_product(self, product_id: str) -> tuple[str, Image.Image] | None:
        product_dir = self.generated_root / product_id
        if not product_dir.exists():
            return None

        candidates = sorted(
            [path for path in product_dir.glob("*.png") if path.is_file()],
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            return None

        latest = candidates[0]
        return latest.stem, Image.open(latest).convert("RGB")

    def load_by_id(self, image_id: str) -> tuple[str, Image.Image] | None:
        target_name = f"{image_id}.png"
        for path in self.generated_root.rglob(target_name):
            if path.is_file():
                return image_id, Image.open(path).convert("RGB")
        return None
