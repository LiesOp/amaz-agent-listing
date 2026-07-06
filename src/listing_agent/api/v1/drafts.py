from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import AuditResult, Draft
from listing_agent.schemas.audit import AuditResultResponse
from listing_agent.schemas.draft import (
    DraftGenerateRequest,
    DraftGenerateResponse,
    DraftResponse,
    DraftRewriteRequest,
    DraftRewriteResponse,
)
from listing_agent.services.audits import AuditError, AuditService
from listing_agent.services.drafts import DraftGenerationError, DraftService

router = APIRouter(prefix="/drafts", tags=["drafts"])
draft_service = DraftService()
audit_service = AuditService()


def _to_draft_response(draft: Draft) -> DraftResponse:
    """Map a persisted Draft to the public response contract."""
    return DraftResponse(
        id=draft.id,
        conversation_id=draft.conversation_id,
        brief_id=draft.brief_id,
        title=draft.title,
        bullets=draft.bullets,
        description_text=draft.description_text,
        search_terms=draft.search_terms,
        generation_context=draft.generation_context,
        version_no=draft.version_no,
        created_at=draft.created_at,
    )


def _to_audit_response(audit: AuditResult) -> AuditResultResponse:
    """Map a persisted AuditResult to the public response contract."""
    return AuditResultResponse(
        id=audit.id,
        draft_id=audit.draft_id,
        status=audit.status,
        risk_score=audit.risk_score,
        findings=audit.findings,
        suggestions=audit.suggestions,
        used_rule_ids=audit.used_rule_ids,
        rule_trace=audit.rule_trace,
        competitor_strategy_trace=audit.competitor_strategy_trace,
        validation_trace=audit.validation_trace,
        created_at=audit.created_at,
    )


@router.post("/generate", response_model=DraftGenerateResponse, status_code=status.HTTP_201_CREATED)
async def generate_draft(
    payload: DraftGenerateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DraftGenerateResponse:
    """Generate title, bullets, description, and Search Terms from the current context."""
    try:
        draft = await draft_service.generate_draft(
            session,
            payload.brief_id,
            custom_prompt=payload.custom_prompt,
        )
        audit = await audit_service.audit_draft(
            session,
            draft.id,
            api_endpoint="POST /api/v1/drafts/generate",
        )
    except DraftGenerationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail == "brief not found"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except AuditError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return DraftGenerateResponse(draft=_to_draft_response(draft), audit=_to_audit_response(audit))


@router.post(
    "/{draft_id}/rewrite",
    response_model=DraftRewriteResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rewrite_draft(
    draft_id: str,
    payload: DraftRewriteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DraftRewriteResponse:
    """Rewrite an existing draft from user instructions and audit findings."""
    try:
        draft = await draft_service.rewrite_draft(session, draft_id, payload.instructions)
        audit = await audit_service.audit_draft(
            session,
            draft.id,
            api_endpoint="POST /api/v1/drafts/{draft_id}/rewrite",
        )
    except DraftGenerationError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail == "draft not found"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    except AuditError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return DraftRewriteResponse(draft=_to_draft_response(draft), audit=_to_audit_response(audit))
