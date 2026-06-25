from datetime import datetime

from pydantic import BaseModel, Field


class AuditCreateRequest(BaseModel):
    """Request body for auditing an existing listing draft."""

    draft_id: str = Field(min_length=1)


class AuditResultResponse(BaseModel):
    """Persisted rule and risk audit result for a draft."""

    id: str
    draft_id: str
    status: str
    risk_score: int
    findings: list[dict] | None
    suggestions: list[str] | None
    used_rule_ids: list[str] | None
    created_at: datetime


class AuditCreateResponse(BaseModel):
    """Audit endpoint response with persisted audit details."""

    audit: AuditResultResponse
