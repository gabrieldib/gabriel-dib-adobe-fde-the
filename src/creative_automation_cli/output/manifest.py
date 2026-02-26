from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class ProductManifestEntry:
    product_id: str
    product_name: str
    hero_source: str
    output_files: dict[str, str] = field(default_factory=dict)
    compliance: dict[str, dict] = field(default_factory=dict)
    legal: dict[str, dict] = field(default_factory=dict)
    skipped: bool = False
    skip_reason: str | None = None


@dataclass(slots=True)
class CampaignManifest:
    campaign_id: str
    target_region: str
    target_audience: str
    message: str
    provider: str
    dry_run: bool
    started_at: str
    locales_processed: list[str] = field(default_factory=lambda: ["en"])
    brand_policy_path: str | None = None
    strict_brand: bool = False
    legal_policy_path: str | None = None
    strict_legal: bool = False
    finished_at: str | None = None
    brand_compliance_summary: dict[str, int] = field(default_factory=dict)
    legal_compliance_summary: dict[str, int] = field(default_factory=dict)
    products: list[ProductManifestEntry] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
