from creative_automation_cli.assets.resolver import ResolvedProductAssets
from creative_automation_cli.models.brief import CampaignBrief
from creative_automation_cli.prompts.builder import build_generation_prompt


def test_prompt_uses_override() -> None:
    brief = CampaignBrief.model_validate(
        {
            "campaign_id": "c1",
            "message": "msg",
            "target_region": "US",
            "target_audience": "Pros",
            "products": [
                {"id": "p1", "name": "One", "prompt": "Custom prompt"},
                {"id": "p2", "name": "Two"},
            ],
        }
    )
    resolved = ResolvedProductAssets(
        product=brief.products[0],
        product_dir=None,
        hero_path=None,
        logo_path=None,
        background_path=None,
        hero_source="generated",
    )
    assert build_generation_prompt(brief, resolved) == "Custom prompt"
