import importlib.util
from typing import Any

from langchain.chat_models import init_chat_model
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.v1_data import ModelConfig, ModelInvocationLog
from listing_agent.services.admin import AdminService, NoActiveModelConfigError


def is_langchain_installed() -> bool:
    return importlib.util.find_spec("langchain") is not None


async def get_active_model_config(session: AsyncSession) -> ModelConfig:
    return await AdminService().get_active_model_config(session)


async def get_chat_model(session: AsyncSession) -> Any:
    model, _model_config = await get_chat_model_with_config(session)
    return model


async def get_chat_model_with_config(session: AsyncSession) -> tuple[Any, ModelConfig]:
    try:
        model_config = await get_active_model_config(session)
    except NoActiveModelConfigError as exc:
        raise RuntimeError("no active model configuration is enabled") from exc

    model_kwargs: dict[str, Any] = {"api_key": model_config.api_key}
    if model_config.base_url:
        model_kwargs["base_url"] = model_config.base_url
    if model_config.thinking_config and model_config.thinking_config != "disabled":
        model_kwargs["extra_body"] = {"thinking": {"type": model_config.thinking_config}}

    model = init_chat_model(
        model_config.model_name,
        model_provider=model_config.provider,
        **model_kwargs,
    )
    return model, model_config


async def record_model_invocation(
    session: AsyncSession,
    *,
    model_config_id: str,
    feature_name: str,
    api_endpoint: str,
    response: dict[str, Any],
) -> None:
    input_tokens, output_tokens, total_tokens = extract_token_usage(response)
    session.add(
        ModelInvocationLog(
            model_config_id=model_config_id,
            feature_name=feature_name,
            api_endpoint=api_endpoint,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
    )
    await session.flush()


def extract_token_usage(response: dict[str, Any]) -> tuple[int, int, int]:
    candidates: list[Any] = []
    messages = response.get("messages")
    if isinstance(messages, list):
        candidates.extend(reversed(messages))
    candidates.append(response)

    for candidate in candidates:
        usage = _read_usage_mapping(getattr(candidate, "usage_metadata", None))
        if usage is not None:
            return usage

        response_metadata = getattr(candidate, "response_metadata", None)
        if isinstance(response_metadata, dict):
            usage = _read_usage_mapping(response_metadata.get("token_usage"))
            if usage is not None:
                return usage
            usage = _read_usage_mapping(response_metadata.get("usage"))
            if usage is not None:
                return usage

        if isinstance(candidate, dict):
            usage = _read_usage_mapping(candidate.get("usage_metadata"))
            if usage is not None:
                return usage
            usage = _read_usage_mapping(candidate.get("token_usage"))
            if usage is not None:
                return usage
            usage = _read_usage_mapping(candidate.get("usage"))
            if usage is not None:
                return usage

    return 0, 0, 0


def _read_usage_mapping(usage: Any) -> tuple[int, int, int] | None:
    if not isinstance(usage, dict):
        return None
    input_tokens = _as_int(
        usage.get("input_tokens")
        or usage.get("prompt_tokens")
        or usage.get("prompt_token_count")
    )
    output_tokens = _as_int(
        usage.get("output_tokens")
        or usage.get("completion_tokens")
        or usage.get("candidates_token_count")
    )
    total_tokens = _as_int(usage.get("total_tokens") or usage.get("total_token_count"))
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    if input_tokens == 0 and output_tokens == 0 and total_tokens == 0:
        return None
    return input_tokens, output_tokens, total_tokens


def _as_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def read_structured_response(
    response: dict[str, Any],
    *,
    schema: type[BaseModel],
) -> dict[str, Any] | None:
    """Read LangChain structured output from an agent response."""
    structured_response = response.get("structured_response")
    if isinstance(structured_response, schema):
        return structured_response.model_dump()
    if isinstance(structured_response, dict):
        return schema.model_validate(structured_response).model_dump()
    return None
