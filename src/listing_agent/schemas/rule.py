from datetime import datetime

from pydantic import BaseModel, Field


class RuleCreateRequest(BaseModel):
    """Payload for manually creating an Amazon listing rule."""

    rule_category: str = Field(min_length=1, max_length=64)
    rule_title: str = Field(min_length=1, max_length=255)
    rule_content: str = Field(min_length=1)
    rule_scope: str = "amazon_listing"
    rule_level: str = "reference"
    priority: int = 100
    is_active: bool = True
    source_note: str | None = None
    created_by: str | None = None
    updated_by: str | None = None


class RuleUpdateRequest(BaseModel):
    """Payload for editing an existing manual rule."""

    rule_category: str = Field(min_length=1, max_length=64)
    rule_title: str = Field(min_length=1, max_length=255)
    rule_content: str = Field(min_length=1)
    rule_scope: str = "amazon_listing"
    rule_level: str = "reference"
    priority: int = 100
    is_active: bool = True
    source_note: str | None = None
    updated_by: str | None = None


class RuleStatusUpdateRequest(BaseModel):
    """Payload for enabling or disabling a manual rule."""

    is_active: bool
    updated_by: str | None = None


class RuleItemResponse(BaseModel):
    """Manually maintained rule row."""

    id: str
    rule_category: str
    rule_title: str
    rule_content: str
    rule_scope: str
    rule_level: str
    priority: int
    is_active: bool
    source_note: str | None
    version_no: int
    created_by: str | None
    updated_by: str | None
    created_at: datetime
    updated_at: datetime


class RuleListResponse(BaseModel):
    """Minimal list wrapper for current rule records."""

    items: list[RuleItemResponse]


class RuleCategoryGroup(BaseModel):
    """Rules grouped by category for generation and audit context loading."""

    category: str
    items: list[RuleItemResponse]


class RuleGroupedResponse(BaseModel):
    """Rule list organized by category."""

    groups: list[RuleCategoryGroup]
