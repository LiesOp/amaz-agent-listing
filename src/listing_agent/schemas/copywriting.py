from datetime import datetime

from pydantic import BaseModel, Field

from listing_agent.schemas.audit import AuditResultResponse
from listing_agent.schemas.brief import BriefResponse
from listing_agent.schemas.draft import DraftResponse


class CopywritingConversationInfo(BaseModel):
    """Compact conversation fields shown in the copywriting list."""

    id: str
    status: str
    current_step: str
    marketplace: str
    language: str
    active_brief_id: str | None
    active_draft_id: str | None
    created_at: datetime
    updated_at: datetime


class CopywritingRecordResponse(BaseModel):
    """One conversation row for the copywriting menu."""

    conversation: CopywritingConversationInfo
    product: BriefResponse | None
    product_name: str | None
    competitor_asins: list[str]
    competitor_analysis_id: str | None
    created_at: datetime


class CopywritingRecordListResponse(BaseModel):
    """Paginated copywriting record list."""

    items: list[CopywritingRecordResponse]
    total: int
    page: int
    page_size: int


class CopywritingDraftAuditPageResponse(BaseModel):
    """One draft and its audits for a paginated detail modal."""

    draft: DraftResponse | None
    audits: list[AuditResultResponse]
    total: int
    page: int
    page_size: int = Field(default=1)
