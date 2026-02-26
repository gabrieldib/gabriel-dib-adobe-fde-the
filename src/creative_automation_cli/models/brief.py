from __future__ import annotations

from pydantic import BaseModel, Field


class VisualStyle(BaseModel):
    keywords: list[str] = Field(default_factory=list)
    mood: str | None = None
    palette: list[str] = Field(default_factory=list)


class ProductBrief(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    prompt: str | None = None
    image: str | None = None
    logo: str | None = None


class CampaignBrief(BaseModel):
    campaign_id: str = Field(min_length=1)
    message: str = Field(min_length=1)
    target_region: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    locals: list[str] = Field(default_factory=list)
    products: list[ProductBrief] = Field(min_length=2)
    visual_style: VisualStyle | None = None
    prompts: dict[str, str] | None = None
    palette: list[str] | None = None
    negative_prompt: str | None = None
