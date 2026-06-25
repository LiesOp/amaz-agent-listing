from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.api.v1.audits import _to_audit_response
from listing_agent.api.v1.briefs import _to_brief_response
from listing_agent.api.v1.drafts import _to_draft_response
from listing_agent.db.session import get_db_session
from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import (
    AuditResult,
    CompetitorAnalysis,
    CompetitorInput,
    Draft,
    ProductBrief,
)
from listing_agent.schemas.copywriting import (
    CopywritingConversationInfo,
    CopywritingDraftAuditPageResponse,
    CopywritingRecordListResponse,
    CopywritingRecordResponse,
)

router = APIRouter(prefix="/copywriting", tags=["copywriting"])


@router.get("/records", response_model=CopywritingRecordListResponse)
async def list_copywriting_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> CopywritingRecordListResponse:
    """Return paginated conversations with product and copywriting context."""
    total_result = await session.execute(select(func.count()).select_from(Conversation))
    total = int(total_result.scalar_one() or 0)

    result = await session.execute(
        select(Conversation)
        .order_by(Conversation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    conversations = list(result.scalars().all())
    items = [await _build_record_response(session, conversation) for conversation in conversations]
    return CopywritingRecordListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/records/{conversation_id}/draft-audits",
    response_model=CopywritingDraftAuditPageResponse,
)
async def list_copywriting_draft_audits(
    conversation_id: str,
    page: int = Query(default=1, ge=1),
    session: AsyncSession = Depends(get_db_session),
) -> CopywritingDraftAuditPageResponse:
    """Return one draft and its audit records per page."""
    total_result = await session.execute(
        select(func.count())
        .select_from(Draft)
        .where(Draft.conversation_id == conversation_id)
    )
    total = int(total_result.scalar_one() or 0)
    draft_result = await session.execute(
        select(Draft)
        .where(Draft.conversation_id == conversation_id)
        .order_by(Draft.created_at.desc())
        .offset(page - 1)
        .limit(1)
    )
    draft = draft_result.scalar_one_or_none()
    audits = []
    if draft is not None:
        audit_result = await session.execute(
            select(AuditResult)
            .where(AuditResult.draft_id == draft.id)
            .order_by(AuditResult.created_at.desc())
        )
        audits = [_to_audit_response(item) for item in audit_result.scalars().all()]

    return CopywritingDraftAuditPageResponse(
        draft=_to_draft_response(draft) if draft is not None else None,
        audits=audits,
        total=total,
        page=page,
        page_size=1,
    )


async def _build_record_response(
    session: AsyncSession,
    conversation: Conversation,
) -> CopywritingRecordResponse:
    brief = await _get_display_brief(session, conversation)
    competitor_asins = await _get_competitor_asins(session, conversation.id, brief.id if brief else None)
    analysis_id = await _get_competitor_analysis_id(
        session,
        conversation.id,
        brief.id if brief else None,
    )
    return CopywritingRecordResponse(
        conversation=CopywritingConversationInfo(
            id=conversation.id,
            status=conversation.status,
            current_step=conversation.current_step,
            marketplace=conversation.marketplace,
            language=conversation.language,
            active_brief_id=conversation.active_brief_id,
            active_draft_id=conversation.active_draft_id,
            created_at=conversation.created_at,
            updated_at=conversation.updated_at,
        ),
        product=_to_brief_response(brief) if brief is not None else None,
        product_name=brief.product_name if brief is not None else None,
        competitor_asins=competitor_asins,
        competitor_analysis_id=analysis_id,
        created_at=conversation.created_at,
    )


async def _get_display_brief(
    session: AsyncSession,
    conversation: Conversation,
) -> ProductBrief | None:
    if conversation.active_brief_id:
        result = await session.execute(
            select(ProductBrief).where(ProductBrief.id == conversation.active_brief_id)
        )
        brief = result.scalar_one_or_none()
        if brief is not None:
            return brief

    result = await session.execute(
        select(ProductBrief)
        .where(ProductBrief.conversation_id == conversation.id)
        .order_by(ProductBrief.updated_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_competitor_asins(
    session: AsyncSession,
    conversation_id: str,
    brief_id: str | None,
) -> list[str]:
    statement = select(CompetitorInput.asin).where(CompetitorInput.conversation_id == conversation_id)
    if brief_id:
        statement = statement.where(CompetitorInput.brief_id == brief_id)
    result = await session.execute(statement.order_by(CompetitorInput.created_at.asc()))
    values = []
    seen = set()
    for asin in result.scalars().all():
        if not asin or asin in seen:
            continue
        seen.add(asin)
        values.append(asin)
    return values


async def _get_competitor_analysis_id(
    session: AsyncSession,
    conversation_id: str,
    brief_id: str | None,
) -> str | None:
    statement = select(CompetitorAnalysis)
    if brief_id:
        statement = statement.where(CompetitorAnalysis.brief_id == brief_id)
    else:
        statement = statement.where(CompetitorAnalysis.conversation_id == conversation_id)
    result = await session.execute(statement.order_by(CompetitorAnalysis.updated_at.desc()).limit(1))
    analysis = result.scalar_one_or_none()
    return analysis.id if analysis is not None else None
