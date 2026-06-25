from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.v1_data import ModelConfig, ModelInvocationLog, Rule


class ModelConfigNotFoundError(Exception):
    """Raised when a model configuration does not exist."""


class NoActiveModelConfigError(Exception):
    """Raised when no model configuration is enabled."""


class AdminService:
    """Read-only management queries for V1 operations."""

    async def get_rule_overview(self, session: AsyncSession) -> dict:
        """Return manual rule inventory and recent edit status."""
        rules = await self._list_recent_rules(session)
        total_rule_count = await self._count_rules(session)
        active_rule_count = await self._count_rules(session, is_active=True)
        hard_rule_count = await self._count_rules(session, rule_level="hard")
        last_rule_updated_at = await self._last_rule_updated_at(session)

        return {
            "total_rule_count": total_rule_count,
            "active_rule_count": active_rule_count,
            "inactive_rule_count": total_rule_count - active_rule_count,
            "hard_rule_count": hard_rule_count,
            "last_rule_updated_at": last_rule_updated_at,
            "recent_rules": rules,
        }

    async def _list_recent_rules(self, session: AsyncSession) -> list[Rule]:
        result = await session.execute(
            select(Rule).order_by(Rule.updated_at.desc()).limit(10)
        )
        return list(result.scalars().all())

    async def _count_rules(
        self,
        session: AsyncSession,
        is_active: bool | None = None,
        rule_level: str | None = None,
    ) -> int:
        statement = select(func.count()).select_from(Rule)
        if is_active is not None:
            statement = statement.where(Rule.is_active == is_active)
        if rule_level is not None:
            statement = statement.where(Rule.rule_level == rule_level)
        result = await session.execute(statement)
        return int(result.scalar_one())

    async def _last_rule_updated_at(self, session: AsyncSession):
        result = await session.execute(select(func.max(Rule.updated_at)))
        return result.scalar_one_or_none()

    async def list_model_configs(self, session: AsyncSession) -> list[ModelConfig]:
        result = await session.execute(
            select(ModelConfig).order_by(ModelConfig.is_active.desc(), ModelConfig.updated_at.desc())
        )
        return list(result.scalars().all())

    async def list_model_invocation_logs(
        self,
        session: AsyncSession,
        model_config_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[ModelInvocationLog], int]:
        await self._get_model_config(session, model_config_id)
        total_result = await session.execute(
            select(func.count())
            .select_from(ModelInvocationLog)
            .where(ModelInvocationLog.model_config_id == model_config_id)
        )
        total = int(total_result.scalar_one())
        result = await session.execute(
            select(ModelInvocationLog)
            .where(ModelInvocationLog.model_config_id == model_config_id)
            .order_by(ModelInvocationLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(result.scalars().all()), total

    async def get_model_config(self, session: AsyncSession, model_config_id: str) -> ModelConfig:
        model_config = await self._get_model_config(session, model_config_id)
        return model_config

    async def get_active_model_config(self, session: AsyncSession) -> ModelConfig:
        result = await session.execute(
            select(ModelConfig).where(ModelConfig.is_active.is_(True)).limit(1)
        )
        model_config = result.scalar_one_or_none()
        if model_config is None:
            raise NoActiveModelConfigError("no active model configuration")
        return model_config

    async def create_model_config(self, session: AsyncSession, values: dict) -> ModelConfig:
        activate = bool(values.pop("is_active", False))
        model_config = ModelConfig(**self._normalize_model_values(values), is_active=False)
        session.add(model_config)
        await session.flush()
        if activate:
            await self._activate_model_config(session, model_config)
        await session.commit()
        await session.refresh(model_config)
        return model_config

    async def update_model_config(
        self,
        session: AsyncSession,
        model_config_id: str,
        values: dict,
    ) -> ModelConfig:
        model_config = await self._get_model_config(session, model_config_id)
        normalized = self._normalize_model_values(values)
        if not normalized.get("api_key"):
            normalized.pop("api_key", None)
        for key, value in normalized.items():
            setattr(model_config, key, value)
        await session.commit()
        await session.refresh(model_config)
        return model_config

    async def activate_model_config(
        self,
        session: AsyncSession,
        model_config_id: str,
    ) -> ModelConfig:
        model_config = await self._get_model_config(session, model_config_id)
        await self._activate_model_config(session, model_config)
        await session.commit()
        await session.refresh(model_config)
        return model_config

    async def delete_model_config(self, session: AsyncSession, model_config_id: str) -> None:
        model_config = await self._get_model_config(session, model_config_id)
        await session.delete(model_config)
        await session.commit()

    async def _get_model_config(self, session: AsyncSession, model_config_id: str) -> ModelConfig:
        result = await session.execute(
            select(ModelConfig).where(ModelConfig.id == model_config_id)
        )
        model_config = result.scalar_one_or_none()
        if model_config is None:
            raise ModelConfigNotFoundError(model_config_id)
        return model_config

    async def _activate_model_config(
        self,
        session: AsyncSession,
        model_config: ModelConfig,
    ) -> None:
        active_result = await session.execute(select(ModelConfig).where(ModelConfig.is_active.is_(True)))
        for active_model in active_result.scalars().all():
            active_model.is_active = False
        model_config.is_active = True
        await session.flush()

    def _normalize_model_values(self, values: dict) -> dict:
        normalized = dict(values)
        for key in ("display_name", "provider", "model_name", "api_key", "base_url", "thinking_config"):
            value = normalized.get(key)
            if isinstance(value, str):
                normalized[key] = value.strip()
        if normalized.get("base_url") == "":
            normalized["base_url"] = None
        if not normalized.get("thinking_config"):
            normalized["thinking_config"] = "disabled"
        return normalized
