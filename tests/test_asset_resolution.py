from pathlib import Path

from creative_automation_cli.assets.resolver import resolve_product_assets
from creative_automation_cli.models.brief import CampaignBrief


def _brief() -> CampaignBrief:
    return CampaignBrief.model_validate(
        {
            "campaign_id": "c1",
            "message": "m",
            "target_region": "US",
            "target_audience": "a",
            "products": [
                {"id": "p1", "name": "One"},
                {"id": "p2", "name": "Two"},
            ],
        }
    )


def test_resolve_reused_and_generated(tmp_path: Path) -> None:
    (tmp_path / "p1").mkdir(parents=True)
    (tmp_path / "p1" / "product.png").write_bytes(b"x")
    resolved = resolve_product_assets(tmp_path, _brief())
    assert resolved[0].hero_source == "reused"
    assert resolved[1].hero_source == "generated"
