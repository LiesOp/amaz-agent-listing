from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.api.v1.rules import _to_rule_response
from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import ModelConfig
from listing_agent.schemas.admin import (
    ModelConfigCreateRequest,
    ModelConfigListResponse,
    ModelConfigResponse,
    ModelConfigUpdateRequest,
    ModelInvocationLogListResponse,
    ModelInvocationLogResponse,
    RuleAdminOverviewResponse,
)
from listing_agent.services.admin import AdminService, ModelConfigNotFoundError

router = APIRouter(prefix="/admin", tags=["admin"])
admin_service = AdminService()


def _to_model_config_response(model_config: ModelConfig) -> ModelConfigResponse:
    return ModelConfigResponse(
        id=model_config.id,
        display_name=model_config.display_name,
        provider=model_config.provider,
        model_name=model_config.model_name,
        base_url=model_config.base_url,
        thinking_config=model_config.thinking_config,
        is_active=model_config.is_active,
        has_api_key=bool(model_config.api_key),
        created_at=model_config.created_at,
        updated_at=model_config.updated_at,
    )


def _to_model_invocation_log_response(log) -> ModelInvocationLogResponse:
    return ModelInvocationLogResponse(
        id=log.id,
        model_config_id=log.model_config_id,
        feature_name=log.feature_name,
        api_endpoint=log.api_endpoint,
        input_tokens=log.input_tokens,
        output_tokens=log.output_tokens,
        total_tokens=log.total_tokens,
        created_at=log.created_at,
    )


@router.get("/rules/overview", response_model=RuleAdminOverviewResponse)
async def get_rule_admin_overview(
    session: AsyncSession = Depends(get_db_session),
) -> RuleAdminOverviewResponse:
    """Return manual rule inventory for admin screens."""
    overview = await admin_service.get_rule_overview(session)
    return RuleAdminOverviewResponse(
        total_rule_count=overview["total_rule_count"],
        active_rule_count=overview["active_rule_count"],
        inactive_rule_count=overview["inactive_rule_count"],
        hard_rule_count=overview["hard_rule_count"],
        last_rule_updated_at=overview["last_rule_updated_at"],
        recent_rules=[_to_rule_response(rule) for rule in overview["recent_rules"]],
    )


@router.get("/models", response_model=ModelConfigListResponse)
async def list_model_configs(
    session: AsyncSession = Depends(get_db_session),
) -> ModelConfigListResponse:
    """Return model configurations for the management screen."""
    model_configs = await admin_service.list_model_configs(session)
    return ModelConfigListResponse(
        items=[_to_model_config_response(model_config) for model_config in model_configs]
    )


@router.get("/models/{model_config_id}/invocations", response_model=ModelInvocationLogListResponse)
async def list_model_invocation_logs(
    model_config_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: AsyncSession = Depends(get_db_session),
) -> ModelInvocationLogListResponse:
    """Return recent model invocation logs for one model configuration."""
    try:
        logs, total = await admin_service.list_model_invocation_logs(
            session,
            model_config_id,
            page,
            page_size,
        )
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model config not found") from exc
    return ModelInvocationLogListResponse(
        items=[_to_model_invocation_log_response(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/models", response_model=ModelConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_model_config(
    payload: ModelConfigCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ModelConfigResponse:
    """Create one model configuration."""
    model_config = await admin_service.create_model_config(session, payload.model_dump())
    return _to_model_config_response(model_config)


@router.put("/models/{model_config_id}", response_model=ModelConfigResponse)
async def update_model_config(
    model_config_id: str,
    payload: ModelConfigUpdateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ModelConfigResponse:
    """Update one model configuration."""
    try:
        model_config = await admin_service.update_model_config(
            session,
            model_config_id,
            payload.model_dump(),
        )
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model config not found") from exc
    return _to_model_config_response(model_config)


@router.patch("/models/{model_config_id}/activate", response_model=ModelConfigResponse)
async def activate_model_config(
    model_config_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> ModelConfigResponse:
    """Enable one model configuration and disable the others."""
    try:
        model_config = await admin_service.activate_model_config(session, model_config_id)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model config not found") from exc
    return _to_model_config_response(model_config)


@router.delete("/models/{model_config_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_model_config(
    model_config_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    """Delete one model configuration."""
    try:
        await admin_service.delete_model_config(session, model_config_id)
    except ModelConfigNotFoundError as exc:
        raise HTTPException(status_code=404, detail="model config not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
