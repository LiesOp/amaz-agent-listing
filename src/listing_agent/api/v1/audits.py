from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import AuditResult
from listing_agent.schemas.audit import (
    AuditCreateRequest,
    AuditCreateResponse,
    AuditResultResponse,
)
from listing_agent.services.audits import AuditError, AuditService

router = APIRouter(prefix="/audits", tags=["audits"])
audit_service = AuditService()


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
        created_at=audit.created_at,
    )


@router.post("/run", response_model=AuditCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_audit(
    payload: AuditCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> AuditCreateResponse:
    """Audit an existing draft and save the risk result."""
    try:
        audit = await audit_service.audit_draft(session, payload.draft_id)
    except AuditError as exc:
        detail = str(exc)
        status_code = (
            status.HTTP_404_NOT_FOUND
            if detail == "draft not found"
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return AuditCreateResponse(audit=_to_audit_response(audit))
