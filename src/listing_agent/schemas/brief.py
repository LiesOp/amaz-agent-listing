from datetime import datetime

from pydantic import BaseModel, Field


class BriefUpsertRequest(BaseModel):
    """Structured product information accepted by the Brief API."""

    conversation_id: str | None = None
    product_name: str | None = Field(default=None, max_length=255)
    brand: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=255)
    marketplace: str = Field(default="US", min_length=1, max_length=16)
    language: str = Field(default="en-US", min_length=2, max_length=32)
    core_features: list[str] | None = None
    materials: list[str] | None = None
    color: str | None = Field(default=None, max_length=255)
    quantity: str | None = Field(default=None, max_length=255)
    size_info: str | None = None
    target_audience: str | None = None
    keywords_seed: list[str] | None = None


class BriefResponse(BaseModel):
    """Persisted Brief state plus generation readiness metadata."""

    id: str
    conversation_id: str
    product_name: str | None
    brand: str | None
    category: str | None
    marketplace: str
    language: str
    core_features: list[str] | None
    materials: list[str] | None
    color: str | None
    quantity: str | None
    size_info: str | None
    target_audience: str | None
    keywords_seed: list[str] | None
    completeness_score: int
    missing_required_fields: list[str]
    is_ready_for_generation: bool
    created_at: datetime
    updated_at: datetime
