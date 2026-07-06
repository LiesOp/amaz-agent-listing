from datetime import datetime

from pydantic import BaseModel, Field

from listing_agent.schemas.audit import AuditResultResponse


class DraftGenerateRequest(BaseModel):
    """Request body for generating listing copy from a ready Brief."""

    brief_id: str = Field(min_length=1)
    custom_prompt: str | None = None


class DraftRewriteRequest(BaseModel):
    """Request body for rewriting an existing draft."""

    instructions: str = Field(min_length=1)


class DescriptionSpecificationResponse(BaseModel):
    """Structured specification fields for the long description."""

    brand: str = ""
    name: str = ""
    color: str = ""
    material: str = ""
    size: str = ""
    applicable: str = ""


class DescriptionFieldsResponse(BaseModel):
    """Frontend-facing long description fields."""

    description_title: str
    specification: DescriptionSpecificationResponse
    features: list[str]


class DraftResponse(BaseModel):
    """Generated listing copy saved as a draft."""

    id: str
    conversation_id: str
    brief_id: str | None
    title: str | None
    bullets: list[str] | None
    description_fields: DescriptionFieldsResponse | None = None
    description_text: str | None
    search_terms: list[str] | None
    generation_context: dict | None
    version_no: int
    created_at: datetime


class DraftGenerateResponse(BaseModel):
    """Generation endpoint response with persisted draft details."""

    draft: DraftResponse
    audit: AuditResultResponse


class DraftRewriteResponse(BaseModel):
    """Rewrite endpoint response with the new draft and audit result."""

    draft: DraftResponse
    audit: AuditResultResponse
