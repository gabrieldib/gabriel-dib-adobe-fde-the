"""Optional AWS S3 mirror for local storage operations.

Activated automatically when ``AWS_ACCESS_KEY_ID`` and
``AWS_SECRET_ACCESS_KEY`` are found in the process environment (loaded from
``.env`` by the CLI before the pipeline runs).

All S3 operations are **best-effort**: errors are logged as warnings and
never propagate to the caller so local-only execution is always safe.

S3 key scheme
-------------
Generated hero images  : ``generated/{product_id}/{image_id}.png``
Campaign output files  : ``output/{path_relative_to_output_root}``
  e.g. ``output/my-campaign/manifest.json``
       ``output/my-campaign/product_1/1x1/final.png``
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

S3_BUCKET = "gabriel-adobe-fde-tha"


class S3Mirror:
    """Mirrors local file writes to an S3 bucket and can fall back to S3 on
    local cache misses."""

    BUCKET = S3_BUCKET

    def __init__(self, client: object) -> None:
        self._client = client

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> S3Mirror | None:
        """Return an :class:`S3Mirror` if AWS credentials are present in *env*,
        otherwise ``None``.

        Credentials read from:

        * ``AWS_ACCESS_KEY_ID``
        * ``AWS_SECRET_ACCESS_KEY``
        * ``AWS_DEFAULT_REGION`` (optional, defaults to ``us-east-1``)
        """
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        if not access_key or not secret_key:
            logger.debug("No AWS credentials found — S3 mirror disabled.")
            return None

        try:
            import boto3  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "AWS credentials are set but boto3 is not installed — S3 mirror disabled. "
                "Install with: pip install -e .[s3]"
            )
            return None

        region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
        client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )
        logger.info("S3 mirror active — bucket: %s, region: %s", cls.BUCKET, region)
        return cls(client)

    # ------------------------------------------------------------------
    # Low-level primitives (swallowed exceptions)
    # ------------------------------------------------------------------

    def upload_file(self, local_path: Path, s3_key: str) -> None:
        """Upload *local_path* to *s3_key*. Non-fatal on error."""
        try:
            self._client.upload_file(str(local_path), self.BUCKET, s3_key)  # type: ignore[attr-defined]
            logger.debug("S3 ↑ %s → s3://%s/%s", local_path.name, self.BUCKET, s3_key)
        except Exception as exc:
            logger.warning("S3 upload failed [key=%s]: %s", s3_key, exc)

    def download_file(self, s3_key: str, local_path: Path) -> bool:
        """Download *s3_key* to *local_path*. Returns ``False`` if key not found."""
        try:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            self._client.download_file(self.BUCKET, s3_key, str(local_path))  # type: ignore[attr-defined]
            logger.debug("S3 ↓ s3://%s/%s → %s", self.BUCKET, s3_key, local_path.name)
            return True
        except Exception:
            return False

    def list_keys(self, prefix: str) -> list[str]:
        """Return all object keys under *prefix*, sorted ascending.

        Empty list on error (e.g. bucket does not exist yet).
        """
        try:
            paginator = self._client.get_paginator("list_objects_v2")  # type: ignore[attr-defined]
            keys: list[str] = []
            for page in paginator.paginate(Bucket=self.BUCKET, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return sorted(keys)
        except Exception as exc:
            logger.warning("S3 list failed [prefix=%s]: %s", prefix, exc)
            return []

    # ------------------------------------------------------------------
    # Domain helpers — generated images
    # ------------------------------------------------------------------

    def _generated_key(self, product_id: str, image_id: str) -> str:
        return f"generated/{product_id}/{image_id}.png"

    def upload_generated_image(self, local_path: Path, product_id: str, image_id: str) -> None:
        """Upload a generated hero image to ``generated/{product_id}/{image_id}.png``."""
        self.upload_file(local_path, self._generated_key(product_id, image_id))

    def upload_asset(self, local_path: Path, asset_filename: str) -> None:
        """Upload a flat named asset to ``generated/{asset_filename}``.

        Used for deterministic assets whose filenames follow the
        ``{type}_{product_id}.png`` pattern.
        """
        self.upload_file(local_path, f"generated/{asset_filename}")

    def download_generated_image(self, product_id: str, image_id: str, dest_path: Path) -> bool:
        """Download ``generated/{product_id}/{image_id}.png`` to *dest_path*."""
        return self.download_file(self._generated_key(product_id, image_id), dest_path)

    def list_generated_for_product(self, product_id: str) -> list[str]:
        """Return image IDs for a product, sorted oldest → newest.

        Key names use a timestamp prefix so alphabetical order is chronological.
        """
        prefix = f"generated/{product_id}/"
        return [
            Path(key).stem  # strip directory prefix and .png extension
            for key in self.list_keys(prefix)
            if key.endswith(".png")
        ]

    def find_generated_image_key(self, image_id: str) -> str | None:
        """Search all products for *image_id* and return the S3 key, or ``None``."""
        target_suffix = f"/{image_id}.png"
        for key in self.list_keys("generated/"):
            if key.endswith(target_suffix):
                return key
        return None

    # ------------------------------------------------------------------
    # Domain helpers — output files
    # ------------------------------------------------------------------

    def upload_output_file(self, local_path: Path, output_root: Path) -> None:
        """Upload an output file using a key derived from its path relative to *output_root*.

        Example: ``output_root=/home/user/output``,
        ``local_path=/home/user/output/my-campaign/manifest.json``
        → S3 key ``output/my-campaign/manifest.json``
        """
        try:
            rel = local_path.relative_to(output_root)
        except ValueError:
            logger.warning(
                "S3 upload skipped: %s is not under output_root %s", local_path, output_root
            )
            return
        s3_key = f"output/{rel.as_posix()}"
        self.upload_file(local_path, s3_key)
