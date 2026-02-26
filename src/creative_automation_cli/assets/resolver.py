from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from creative_automation_cli.models.brief import CampaignBrief, ProductBrief


@dataclass(slots=True)
class ResolvedProductAssets:
    product: ProductBrief
    product_dir: Path
    hero_path: Path | None
    logo_path: Path | None
    background_path: Path | None
    hero_source: str


def _resolve_file(path: Path) -> Path | None:
    return path if path.exists() else None


def resolve_product_assets(assets_root: Path, brief: CampaignBrief) -> list[ResolvedProductAssets]:
    resolved: list[ResolvedProductAssets] = []
    for product in brief.products:
        product_dir = assets_root / product.id
        image_name = product.image or "product.png"
        logo_name = product.logo or "logo.png"

        hero_path = _resolve_file(product_dir / image_name)
        logo_path = _resolve_file(product_dir / logo_name)
        background_path = _resolve_file(product_dir / "background.png")

        resolved.append(
            ResolvedProductAssets(
                product=product,
                product_dir=product_dir,
                hero_path=hero_path,
                logo_path=logo_path,
                background_path=background_path,
                hero_source="reused" if hero_path else "generated",
            )
        )
    return resolved
