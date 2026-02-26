"""Tests for flat-asset storage: ensure_product_assets saves type_{product_id}.png
files directly into storage/generated/ (no per-product subfolder), and those
files are picked up by the pipeline so hero_source reflects the reused asset."""
from pathlib import Path

from PIL import Image

from creative_automation_cli.assets.generator import ensure_product_assets
from creative_automation_cli.assets.resolver import ResolvedProductAssets, resolve_product_assets
from creative_automation_cli.brief_loader import load_and_validate_brief
from creative_automation_cli.pipeline import RunConfig, run_pipeline
from creative_automation_cli.providers.mock import MockImageProvider
from creative_automation_cli.storage.generated_store import GeneratedImageStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_brief(path: Path, products: list[dict] | None = None) -> Path:
    brief_file = path / "brief.yaml"
    if products is None:
        products = [{"id": "p1", "name": "Product One"}, {"id": "p2", "name": "Product Two"}]
    product_lines = "\n".join(
        f"  - id: {p['id']}\n    name: {p['name']}" for p in products
    )
    brief_file.write_text(
        f"""campaign_id: flat_storage_demo
message: Test campaign headline
target_region: US
target_audience: General audience
products:
{product_lines}
""",
        encoding="utf-8",
    )
    return brief_file


# ---------------------------------------------------------------------------
# Unit-level: ensure_product_assets writes flat files to storage/generated/
# ---------------------------------------------------------------------------


def test_ensure_product_assets_saves_flat_files(tmp_path: Path) -> None:
    """All three asset types are saved as type_{id}.png directly under storage/generated/."""
    brief_file = _write_brief(tmp_path)
    brief = load_and_validate_brief(brief_file)

    assets_root = tmp_path / "assets"
    storage_root = tmp_path / "storage"
    storage_root.mkdir()
    (storage_root / "generated").mkdir()

    resolved_assets = resolve_product_assets(assets_root, brief)
    store = GeneratedImageStore(storage_root)
    provider = MockImageProvider()

    for resolved in resolved_assets:
        assert resolved.hero_path is None
        assert resolved.logo_path is None
        assert resolved.background_path is None

        updated = ensure_product_assets(resolved, brief, provider, store)

        pid = resolved.product.id
        gen_dir = storage_root / "generated"

        assert updated.hero_path == gen_dir / f"product_{pid}.png"
        assert updated.logo_path == gen_dir / f"logo_{pid}.png"
        assert updated.background_path == gen_dir / f"background_{pid}.png"

        assert updated.hero_path is not None
        assert updated.logo_path is not None
        assert updated.background_path is not None

        assert updated.hero_path.exists()
        assert updated.logo_path.exists()
        assert updated.background_path.exists()

        # Validate the files are valid PNG images
        img = Image.open(updated.hero_path)
        assert img.size[0] > 0 and img.size[1] > 0


def test_ensure_product_assets_skips_existing_assets(tmp_path: Path) -> None:
    """ensure_product_assets does NOT overwrite assets that are already resolved."""
    brief_file = _write_brief(tmp_path, products=[
        {"id": "p1", "name": "One"},
        {"id": "p2", "name": "Two"},
    ])
    brief = load_and_validate_brief(brief_file)

    assets_root = tmp_path / "assets"
    storage_root = tmp_path / "storage"
    (storage_root / "generated").mkdir(parents=True)

    resolved_list = resolve_product_assets(assets_root, brief)
    resolved = resolved_list[0]  # p1
    store = GeneratedImageStore(storage_root)
    provider = MockImageProvider()

    # Pre-create an existing asset file for hero
    existing_hero = tmp_path / "existing_hero.png"
    Image.new("RGB", (32, 32), (123, 45, 67)).save(existing_hero)
    resolved.hero_path = existing_hero

    updated = ensure_product_assets(resolved, brief, provider, store)

    # hero_path should still point to the original file (not regenerated)
    assert updated.hero_path == existing_hero
    # logo and background were absent, so they should now be generated
    assert updated.logo_path is not None
    assert updated.background_path is not None


# ---------------------------------------------------------------------------
# Integration: run_pipeline generates flat assets and marks them as reused
# ---------------------------------------------------------------------------


def test_pipeline_generates_flat_assets_when_missing(tmp_path: Path) -> None:
    """Full pipeline run: missing assets are generated, hero ends up reused from
    the flat-stored asset (hero_source == 'reused')."""
    brief_file = _write_brief(tmp_path, products=[
        {"id": "prod1", "name": "Product Alpha"},
        {"id": "prod2", "name": "Product Beta"},
    ])
    storage_root = tmp_path / "storage"
    (storage_root / "generated").mkdir(parents=True)

    config = RunConfig(
        brief_path=brief_file,
        assets_root=tmp_path / "assets",
        output_root=tmp_path / "output",
        provider_mode="mock",
        gemini_backend="developer",
        gemini_model="gemini-2.5-flash-image",
        locale=None,
        localize=False,
        dry_run=False,
        storage_root=storage_root,
    )
    manifest, metrics = run_pipeline(config)

    gen_dir = storage_root / "generated"
    for pid in ("prod1", "prod2"):
        assert (gen_dir / f"product_{pid}.png").exists()
        assert (gen_dir / f"logo_{pid}.png").exists()
        assert (gen_dir / f"background_{pid}.png").exists()

    products = manifest["products"]
    assert len(products) == 2
    assert metrics["total_products_processed"] == 2

