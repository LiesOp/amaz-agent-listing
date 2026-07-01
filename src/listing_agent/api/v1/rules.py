from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import Rule
from listing_agent.schemas.rule import (
    RuleCategoryGroup,
    RuleCreateRequest,
    RuleGroupedResponse,
    RuleItemResponse,
    RuleListResponse,
    RuleStatusUpdateRequest,
    RuleUpdateRequest,
)
from listing_agent.services.rules import RuleManagementService, RuleNotFoundError

router = APIRouter(prefix="/rules", tags=["rules"])
rule_service = RuleManagementService()


def _to_rule_response(rule: Rule) -> RuleItemResponse:
    """Map a manual rule ORM row to an API response."""
    return RuleItemResponse(
        id=rule.id,
        rule_category=rule.rule_category,
        rule_title=rule.rule_title,
        rule_content=rule.rule_content,
        rule_schema=rule.rule_schema,
        rule_scope=rule.rule_scope,
        rule_level=rule.rule_level,
        priority=rule.priority,
        is_active=rule.is_active,
        source_note=rule.source_note,
        version_no=rule.version_no,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


@router.get("", response_model=RuleListResponse | RuleGroupedResponse)
async def list_rules(
    category: str | None = None,
    rule_level: str | None = None,
    is_active: bool | None = Query(default=None),
    keyword: str | None = None,
    group_by_category: bool = Query(default=False),
    session: AsyncSession = Depends(get_db_session),
) -> RuleListResponse | RuleGroupedResponse:
    """Return manually maintained rules for management, generation, and audit."""
    rules = await rule_service.list_rules(
        session,
        category=category,
        rule_level=rule_level,
        is_active=is_active,
        keyword=keyword,
    )
    if group_by_category:
        groups = [
            RuleCategoryGroup(
                category=category_name,
                items=[_to_rule_response(rule) for rule in category_rules],
            )
            for category_name, category_rules in rule_service.group_rules_by_category(rules).items()
        ]
        return RuleGroupedResponse(groups=groups)

    return RuleListResponse(items=[_to_rule_response(rule) for rule in rules])


@router.post("", response_model=RuleItemResponse, status_code=status.HTTP_201_CREATED)
async def create_rule(
    payload: RuleCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RuleItemResponse:
    """Create one manually maintained Amazon listing rule."""
    rule = await rule_service.create_rule(session, payload.model_dump())
    return _to_rule_response(rule)


@router.get("/{rule_id}", response_model=RuleItemResponse)
async def get_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> RuleItemResponse:
    """Return one manually maintained rule."""
    try:
        rule = await rule_service.get_rule(session, rule_id)
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    return _to_rule_response(rule)


@router.put("/{rule_id}", response_model=RuleItemResponse)
async def update_rule(
    rule_id: str,
    payload: RuleUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RuleItemResponse:
    """Update one manually maintained rule."""
    try:
        rule = await rule_service.update_rule(session, rule_id, payload.model_dump())
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    return _to_rule_response(rule)


@router.patch("/{rule_id}/status", response_model=RuleItemResponse)
async def update_rule_status(
    rule_id: str,
    payload: RuleStatusUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> RuleItemResponse:
    """Enable or disable one manually maintained rule."""
    try:
        rule = await rule_service.set_rule_status(
            session,
            rule_id,
            payload.is_active,
            updated_by=payload.updated_by,
        )
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    return _to_rule_response(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Permanently delete one manual rule."""
    try:
        await rule_service.delete_rule(session, rule_id)
    except RuleNotFoundError as exc:
        raise HTTPException(status_code=404, detail="rule not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
