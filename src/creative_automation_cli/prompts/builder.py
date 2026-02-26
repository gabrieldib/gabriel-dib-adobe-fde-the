from __future__ import annotations

from creative_automation_cli.assets.resolver import ResolvedProductAssets
from creative_automation_cli.models.brief import CampaignBrief


def build_generation_prompt(brief: CampaignBrief, resolved_assets: ResolvedProductAssets) -> str:
    product = resolved_assets.product
    if product.prompt:
        return product.prompt

    style_keywords = ", ".join(brief.visual_style.keywords) if brief.visual_style and brief.visual_style.keywords else ""
    mood = brief.visual_style.mood if brief.visual_style and brief.visual_style.mood else ""

    parts = [
        f"Create a premium advertising hero image for product: {product.name}.",
        f"Target audience: {brief.target_audience}.",
        f"Target region: {brief.target_region}.",
    ]

    if style_keywords:
        parts.append(f"Visual style keywords: {style_keywords}.")
    if mood:
        parts.append(f"Mood: {mood}.")

    parts.append("No text overlays in the generated image.")
    return " ".join(parts)
