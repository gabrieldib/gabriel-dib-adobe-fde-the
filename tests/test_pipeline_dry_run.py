from pathlib import Path

from creative_automation_cli.pipeline import RunConfig, run_pipeline


def test_pipeline_dry_run_writes_manifest_and_metrics(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: demo
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

    config = RunConfig(
        brief_path=brief_file,
        assets_root=tmp_path / "assets",
        output_root=tmp_path / "output",
        provider_mode="mock",
        gemini_backend="developer",
        gemini_model="gemini-2.0-flash-preview-image-generation",
        locale=None,
        dry_run=True,
    )
    manifest, metrics = run_pipeline(config)
    assert manifest["campaign_id"] == "demo"
    assert metrics["total_variants_produced"] == 6
    assert (tmp_path / "output" / "demo" / "manifest.json").exists()
    assert (tmp_path / "output" / "demo" / "metrics.json").exists()
    assert not (tmp_path / "output" / "demo" / "p1" / "1x1" / "final.png").exists()
