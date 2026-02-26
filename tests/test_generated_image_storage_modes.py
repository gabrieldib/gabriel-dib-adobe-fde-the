from pathlib import Path

from PIL import Image

from creative_automation_cli.pipeline import RunConfig, run_pipeline


def test_generated_image_mode_last_reuses_stored_image(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: storage_demo
message: headline
target_region: US
target_audience: audience
products:
  - id: p1
    name: One
  - id: p2
    name: Two
""".strip(),
        encoding="utf-8",
    )

    storage_root = tmp_path / "storage"
    p1_store = storage_root / "generated" / "p1"
    p2_store = storage_root / "generated" / "p2"
    p1_store.mkdir(parents=True, exist_ok=True)
    p2_store.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (20, 30, 40)).save(p1_store / "sample_id_1.png")
    Image.new("RGB", (64, 64), (50, 60, 70)).save(p2_store / "sample_id_2.png")

    config = RunConfig(
        brief_path=brief_file,
        assets_root=tmp_path / "assets",
        output_root=tmp_path / "output",
        provider_mode="mock",
        gemini_backend="developer",
        gemini_model="gemini-2.5-flash-image",
        locale=None,
        localize=False,
        dry_run=True,
        generated_image_mode="last",
        storage_root=storage_root,
    )
    manifest, metrics = run_pipeline(config)

    assert metrics["assets_reused"] == 2
    assert metrics["assets_generated"] == 0
    assert all(product["hero_source"] == "generated_last" for product in manifest["products"])
