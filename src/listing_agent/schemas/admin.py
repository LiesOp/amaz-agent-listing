from datetime import datetime

from pydantic import BaseModel, Field

from listing_agent.schemas.rule import RuleItemResponse


class RuleAdminOverviewResponse(BaseModel):
    """Basic management view for manually maintained rules."""

    total_rule_count: int
    active_rule_count: int
    inactive_rule_count: int
    hard_rule_count: int
    last_rule_updated_at: datetime | None
    recent_rules: list[RuleItemResponse]


class ModelConfigCreateRequest(BaseModel):
    """Payload for creating an LLM model configuration."""

    display_name: str = Field(min_length=1, max_length=128)
    provider: str = Field(default="openai", min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str = Field(min_length=1)
    base_url: str | None = None
    thinking_config: str = Field(default="disabled", max_length=32)
    is_active: bool = False


class ModelConfigUpdateRequest(BaseModel):
    """Payload for editing an existing LLM model configuration."""

    display_name: str = Field(min_length=1, max_length=128)
    provider: str = Field(default="openai", min_length=1, max_length=64)
    model_name: str = Field(min_length=1, max_length=128)
    api_key: str | None = None
    base_url: str | None = None
    thinking_config: str = Field(default="disabled", max_length=32)


class ModelConfigResponse(BaseModel):
    """LLM model configuration without exposing the API key."""

    id: str
    display_name: str
    provider: str
    model_name: str
    base_url: str | None
    thinking_config: str
    is_active: bool
    has_api_key: bool
    created_at: datetime
    updated_at: datetime


class ModelConfigListResponse(BaseModel):
    """List wrapper for model configurations."""

    items: list[ModelConfigResponse]


class ModelInvocationLogResponse(BaseModel):
    """One recorded model invocation."""

    id: str
    model_config_id: str
    feature_name: str
    api_endpoint: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    created_at: datetime


class ModelInvocationLogListResponse(BaseModel):
    """List wrapper for model invocation logs."""

    items: list[ModelInvocationLogResponse]
    total: int
    page: int
    page_size: int
