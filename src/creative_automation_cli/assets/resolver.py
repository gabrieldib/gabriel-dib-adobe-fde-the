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


def _resolve_hero(product_dir: Path, product: "ProductBrief") -> Path | None:
    if product.image:
        return _resolve_file(product_dir / product.image)
    return _resolve_file(product_dir / "product.png") or _resolve_file(
        product_dir / f"product_{product.id}.png"
    )


def _resolve_logo(product_dir: Path, product: "ProductBrief") -> Path | None:
    if product.logo:
        return _resolve_file(product_dir / product.logo)
    return _resolve_file(product_dir / "logo.png") or _resolve_file(
        product_dir / f"logo_{product.id}.png"
    )


def _resolve_background(product_dir: Path, product: "ProductBrief") -> Path | None:
    return _resolve_file(product_dir / "background.png") or _resolve_file(
        product_dir / f"background_{product.id}.png"
    )


def resolve_product_assets(assets_root: Path, brief: CampaignBrief) -> list[ResolvedProductAssets]:
    resolved: list[ResolvedProductAssets] = []
    for product in brief.products:
        product_dir = assets_root / product.id

        hero_path = _resolve_hero(product_dir, product)
        logo_path = _resolve_logo(product_dir, product)
        background_path = _resolve_background(product_dir, product)

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
