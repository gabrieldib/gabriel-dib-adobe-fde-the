from pathlib import Path

from creative_automation_cli.pipeline import RunConfig, run_pipeline


def test_pipeline_localize_generates_locale_specific_outputs(tmp_path: Path) -> None:
    brief_file = tmp_path / "brief.yaml"
    brief_file.write_text(
        """
campaign_id: localize_demo
message: headline
target_region: US
target_audience: audience
locals:
  - es
  - pt-BR
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
        gemini_model="gemini-2.5-flash-image",
        locale=None,
        localize=True,
        dry_run=True,
    )

    manifest, metrics = run_pipeline(config)
    assert manifest["locales_processed"] == ["en", "es", "pt_br"]
    assert metrics["total_variants_produced"] == 18

    product_outputs = manifest["products"][0]["output_files"]
    assert "1x1" in product_outputs
    assert "1x1_es" in product_outputs
    assert "1x1_pt_br" in product_outputs
    assert product_outputs["1x1"].endswith("final.png")
    assert product_outputs["1x1_es"].endswith("final_es.png")
    assert product_outputs["1x1_pt_br"].endswith("final_pt_br.png")
