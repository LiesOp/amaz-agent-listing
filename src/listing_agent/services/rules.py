from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.v1_data import Rule


class RuleNotFoundError(Exception):
    """Raised when a rule ID does not exist."""


class RuleManagementService:
    """Manage manually maintained Amazon listing rules."""

    async def list_rules(
        self,
        session: AsyncSession,
        category: str | None = None,
        rule_level: str | None = None,
        is_active: bool | None = True,
        keyword: str | None = None,
    ) -> list[Rule]:
        """Return rule rows with filters for the rule management screen."""
        statement = select(Rule).order_by(
            Rule.rule_category,
            Rule.priority,
            Rule.updated_at.desc(),
        )
        if category:
            statement = statement.where(Rule.rule_category == category)
        if rule_level:
            statement = statement.where(Rule.rule_level == rule_level)
        if is_active is not None:
            statement = statement.where(Rule.is_active == is_active)
        if keyword:
            pattern = f"%{keyword.strip()}%"
            statement = statement.where(
                Rule.rule_title.ilike(pattern) | Rule.rule_content.ilike(pattern)
            )
        result = await session.execute(statement)
        return list(result.scalars().all())

    async def get_rule(self, session: AsyncSession, rule_id: str) -> Rule:
        """Load one rule by ID."""
        result = await session.execute(select(Rule).where(Rule.id == rule_id))
        rule = result.scalar_one_or_none()
        if rule is None:
            raise RuleNotFoundError(rule_id)
        return rule

    async def create_rule(self, session: AsyncSession, payload: dict) -> Rule:
        """Create a manually maintained rule."""
        rule = Rule(**self._clean_payload(payload))
        session.add(rule)
        await session.commit()
        await session.refresh(rule)
        return rule

    async def update_rule(self, session: AsyncSession, rule_id: str, payload: dict) -> Rule:
        """Replace editable fields for one rule and increment its version."""
        rule = await self.get_rule(session, rule_id)
        values = self._clean_payload(payload, partial=True)
        for field, value in values.items():
            setattr(rule, field, value)
        rule.version_no += 1
        await session.commit()
        await session.refresh(rule)
        return rule

    async def set_rule_status(
        self,
        session: AsyncSession,
        rule_id: str,
        is_active: bool,
        updated_by: str | None = None,
    ) -> Rule:
        """Enable or disable one rule."""
        rule = await self.get_rule(session, rule_id)
        rule.is_active = is_active
        rule.updated_by = updated_by
        rule.version_no += 1
        await session.commit()
        await session.refresh(rule)
        return rule

    async def delete_rule(self, session: AsyncSession, rule_id: str) -> None:
        """Permanently delete one manual rule."""
        rule = await self.get_rule(session, rule_id)
        await session.delete(rule)
        await session.commit()

    def group_rules_by_category(self, rules: list[Rule]) -> dict[str, list[Rule]]:
        """Group rules by category while preserving service ordering."""
        grouped: dict[str, list[Rule]] = {}
        for rule in rules:
            grouped.setdefault(rule.rule_category, []).append(rule)
        return grouped

    def _clean_payload(self, payload: dict, partial: bool = False) -> dict:
        allowed_fields = {
            "rule_category",
            "rule_title",
            "rule_content",
            "rule_scope",
            "rule_level",
            "priority",
            "is_active",
            "source_note",
            "created_by",
            "updated_by",
        }
        values = {key: value for key, value in payload.items() if key in allowed_fields}

        if not partial:
            values.setdefault("rule_scope", "amazon_listing")
            values.setdefault("rule_level", "reference")
            values.setdefault("priority", 100)
            values.setdefault("is_active", True)

        return values
