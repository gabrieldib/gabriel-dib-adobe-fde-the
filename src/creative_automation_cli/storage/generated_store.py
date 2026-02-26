"""Local generated-image store with optional S3 mirror.

When an :class:`~creative_automation_cli.storage.S3Mirror` is supplied,
every write is also uploaded to S3 and every read falls back to S3 if
the local file is missing.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from PIL import Image

from creative_automation_cli.storage.s3_mirror import S3Mirror


class GeneratedImageStore:
    def __init__(self, storage_root: Path, s3_mirror: S3Mirror | None = None):
        self.storage_root = storage_root
        self.generated_root = storage_root / "generated"
        self.generated_root.mkdir(parents=True, exist_ok=True)
        self._s3 = s3_mirror

    def save_new(self, product_id: str, image: Image.Image) -> tuple[str, Path]:
        image_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}_{uuid4().hex[:8]}"
        product_dir = self.generated_root / product_id
        product_dir.mkdir(parents=True, exist_ok=True)
        image_path = product_dir / f"{image_id}.png"
        image.save(image_path, format="PNG")
        if self._s3 is not None:
            self._s3.upload_generated_image(image_path, product_id, image_id)
        return image_id, image_path

    def load_last_for_product(self, product_id: str) -> tuple[str, Image.Image] | None:
        product_dir = self.generated_root / product_id
        candidates: list[Path] = []
        if product_dir.exists():
            candidates = sorted(
                [path for path in product_dir.glob("*.png") if path.is_file()],
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
        if candidates:
            latest = candidates[0]
            return latest.stem, Image.open(latest).convert("RGB")

        # Local cache miss — try S3
        if self._s3 is not None:
            image_ids = self._s3.list_generated_for_product(product_id)
            if image_ids:
                latest_id = image_ids[-1]  # timestamp-sorted: last = most recent
                dest_path = self.generated_root / product_id / f"{latest_id}.png"
                if self._s3.download_generated_image(product_id, latest_id, dest_path):
                    return latest_id, Image.open(dest_path).convert("RGB")

        return None

    def load_by_id(self, image_id: str) -> tuple[str, Image.Image] | None:
        target_name = f"{image_id}.png"
        for path in self.generated_root.rglob(target_name):
            if path.is_file():
                return image_id, Image.open(path).convert("RGB")

        # Local cache miss — try S3
        if self._s3 is not None:
            s3_key = self._s3.find_generated_image_key(image_id)
            if s3_key is not None:
                # Reconstruct the local path from the S3 key: generated/{product_id}/{image_id}.png
                parts = s3_key.split("/")
                if len(parts) == 3:  # generated, product_id, filename
                    product_id = parts[1]
                    dest_path = self.generated_root / product_id / target_name
                    if self._s3.download_generated_image(product_id, image_id, dest_path):
                        return image_id, Image.open(dest_path).convert("RGB")

        return None
