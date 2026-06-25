from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import ProductBrief
from listing_agent.schemas.brief import BriefResponse, BriefUpsertRequest
from listing_agent.services.briefs import (
    BriefNotFoundError,
    BriefService,
    BriefValidationError,
    get_missing_required_fields,
    is_ready_for_generation,
)
from listing_agent.services.conversations import ConversationNotFoundError

router = APIRouter(prefix="/briefs", tags=["briefs"])
brief_service = BriefService()


def _to_brief_response(brief: ProductBrief) -> BriefResponse:
    """Map ORM Brief objects to API responses with readiness metadata."""
    missing_fields = get_missing_required_fields(brief)
    return BriefResponse(
        id=brief.id,
        conversation_id=brief.conversation_id,
        product_name=brief.product_name,
        brand=brief.brand,
        category=brief.category,
        marketplace=brief.marketplace,
        language=brief.language,
        core_features=brief.core_features,
        materials=brief.materials,
        color=brief.color,
        quantity=brief.quantity,
        size_info=brief.size_info,
        target_audience=brief.target_audience,
        keywords_seed=brief.keywords_seed,
        completeness_score=brief.completeness_score,
        missing_required_fields=missing_fields,
        is_ready_for_generation=is_ready_for_generation(brief),
        created_at=brief.created_at,
        updated_at=brief.updated_at,
    )


@router.post("", response_model=BriefResponse, status_code=status.HTTP_201_CREATED)
async def create_brief(
    payload: BriefUpsertRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BriefResponse:
    """Create a product Brief for an existing conversation."""
    try:
        brief = await brief_service.create_brief(session, payload)
    except BriefValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="conversation not found") from exc
    return _to_brief_response(brief)


@router.put("/{brief_id}", response_model=BriefResponse)
async def update_brief(
    brief_id: str,
    payload: BriefUpsertRequest,
    session: AsyncSession = Depends(get_db_session),
) -> BriefResponse:
    """Save or update structured product information."""
    try:
        brief = await brief_service.update_brief(session, brief_id, payload)
    except BriefNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brief not found") from exc
    return _to_brief_response(brief)


@router.get("/{brief_id}", response_model=BriefResponse)
async def get_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> BriefResponse:
    """Return a Brief and whether it is ready for copy generation."""
    try:
        brief = await brief_service.get_brief(session, brief_id)
    except BriefNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="brief not found") from exc
    return _to_brief_response(brief)
