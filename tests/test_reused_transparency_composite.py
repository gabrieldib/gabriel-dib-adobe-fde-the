from pathlib import Path

from PIL import Image

from creative_automation_cli.assets.resolver import ResolvedProductAssets
from creative_automation_cli.models.brief import ProductBrief
from creative_automation_cli.pipeline import _compose_reused_variant, _target_size_from_product


def test_target_sizes_follow_product_dimension_heuristics() -> None:
    assert _target_size_from_product((500, 300), "1x1") == (500, 500)
    assert _target_size_from_product((500, 300), "9x16") == (500, 889)
    assert _target_size_from_product((500, 300), "16x9") == (533, 300)


def test_transparent_product_composited_over_background_for_1x1(tmp_path: Path) -> None:
    product_path = tmp_path / "product.png"
    background_path = tmp_path / "background.png"

    background = Image.new("RGB", (2, 3), (10, 20, 200))
    background.save(background_path)

    product = Image.new("RGBA", (6, 4), (255, 0, 0, 0))
    product.putpixel((2, 2), (255, 0, 0, 255))
    product.save(product_path)

    resolved = ResolvedProductAssets(
        product=ProductBrief(id="p1", name="Product One"),
        product_dir=tmp_path,
        hero_path=product_path,
        logo_path=None,
        background_path=background_path,
        hero_source="reused",
    )

    composed = _compose_reused_variant(resolved, "1x1")
    assert composed.mode == "RGB"
    assert composed.size == (6, 6)
    assert composed.getpixel((0, 0)) == (10, 20, 200)
    assert composed.getpixel((2, 3)) == (255, 0, 0)
