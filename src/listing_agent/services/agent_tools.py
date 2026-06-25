from typing import Any, Literal

from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.v1_data import CompetitorAnalysis, CompetitorSummary, Rule


class ListingRulesToolInput(BaseModel):
    """Input contract for querying listing rules from persistent storage."""

    marketplace: str = Field(default="US")
    category: str | None = None
    fields: list[str] = Field(default_factory=list)
    rule_levels: list[str] = Field(default_factory=list)
    max_rules: int = Field(default=20, ge=1, le=100)
    purpose: Literal["generate", "audit", "rewrite"] = "generate"


class CompetitorAnalysisToolInput(BaseModel):
    """Input contract for querying persisted competitor analysis."""

    brief_id: str | None = None
    fields: list[str] = Field(default_factory=list)
    max_competitors: int = Field(default=5, ge=1, le=20)
    include_raw_copy: bool = False
    purpose: Literal["generate", "audit", "rewrite"] = "generate"


def build_listing_agent_tools(
    session: AsyncSession,
    *,
    brief_id: str | None = None,
) -> list[BaseTool]:
    """Build database-backed tools for listing agents."""

    @tool(
        "listing_rules_tool",
        args_schema=ListingRulesToolInput,
        description=(
            "Query active Amazon listing rules by marketplace, category, field, "
            "rule level, and usage purpose. Use this before generating, auditing, "
            "or rewriting listing copy."
        ),
    )
    async def listing_rules_tool(
        marketplace: str = "US",
        category: str | None = None,
        fields: list[str] | None = None,
        rule_levels: list[str] | None = None,
        max_rules: int = 20,
        purpose: Literal["generate", "audit", "rewrite"] = "generate",
    ) -> dict[str, Any]:
        requested_fields = [field.strip() for field in fields or [] if field.strip()]
        requested_levels = [level.strip() for level in rule_levels or [] if level.strip()]
        statement = (
            select(Rule)
            .where(Rule.is_active.is_(True))
            .order_by(Rule.rule_category, Rule.priority, Rule.created_at.desc())
        )
        if requested_fields:
            statement = statement.where(Rule.rule_category.in_(requested_fields))
        if requested_levels:
            statement = statement.where(Rule.rule_level.in_(requested_levels))
        result = await session.execute(statement.limit(max_rules))
        rules = list(result.scalars().all())
        return {
            "rules": [
                {
                    "id": rule.id,
                    "category": rule.rule_category,
                    "title": rule.rule_title,
                    "content": rule.rule_content,
                    "level": rule.rule_level,
                    "priority": rule.priority,
                    "version_no": rule.version_no,
                    "source_note": rule.source_note,
                }
                for rule in rules
            ],
            "rule_count": len(rules),
            "filters": {
                "marketplace": marketplace,
                "category": category,
                "fields": requested_fields,
                "rule_levels": requested_levels,
                "purpose": purpose,
            },
        }

    @tool(
        "competitor_analysis_tool",
        args_schema=CompetitorAnalysisToolInput,
        description=(
            "Query persisted competitor analysis for a product brief. Use this to "
            "retrieve competitor features, keywords, risks, and differentiation "
            "opportunities without copying competitor text."
        ),
    )
    async def competitor_analysis_tool(
        brief_id: str | None = None,
        fields: list[str] | None = None,
        max_competitors: int = 5,
        include_raw_copy: bool = False,
        purpose: Literal["generate", "audit", "rewrite"] = "generate",
    ) -> dict[str, Any]:
        effective_brief_id = brief_id or build_listing_agent_tools_brief_id
        requested_fields = [field.strip() for field in fields or [] if field.strip()]
        if not effective_brief_id:
            return {
                "competitor_count": 0,
                "analysis_status": "not_available",
                "action_brief": empty_action_brief(),
                "constraints": empty_constraints(),
                "filters": {
                    "brief_id": None,
                    "fields": requested_fields,
                    "purpose": purpose,
                },
            }
        aggregate_result = await session.execute(
            select(CompetitorAnalysis).where(CompetitorAnalysis.brief_id == effective_brief_id)
        )
        persisted_analysis = aggregate_result.scalar_one_or_none()
        if persisted_analysis is not None:
            action_brief = (
                persisted_analysis.action_brief
                if isinstance(persisted_analysis.action_brief, dict)
                else empty_action_brief()
            )
            constraints = (
                persisted_analysis.constraints
                if isinstance(persisted_analysis.constraints, dict)
                else empty_constraints()
            )
            return {
                "competitor_count": persisted_analysis.competitor_count,
                "analysis_status": persisted_analysis.status,
                "action_brief": action_brief,
                "constraints": constraints,
                "usage_guidance": {
                    "role": "generation_plan_and_constraints",
                    "use_action_brief_as_generation_plan": True,
                    "treat_constraints_as_hard_limits": True,
                    "do_not_copy_competitor_text": True,
                    "do_not_treat_competitor_facts_as_own_product_facts": True,
                },
                "filters": {
                    "brief_id": effective_brief_id,
                    "fields": requested_fields,
                    "purpose": purpose,
                    "include_raw_copy": include_raw_copy,
                },
            }
        result = await session.execute(
            select(CompetitorSummary)
            .where(CompetitorSummary.brief_id == effective_brief_id)
            .order_by(CompetitorSummary.created_at.desc())
            .limit(max_competitors)
        )
        summaries = list(result.scalars().all())
        return {
            "competitor_count": len(summaries),
            "analysis_status": "not_generated",
            "action_brief": empty_action_brief(),
            "constraints": empty_constraints(),
            "usage_guidance": {
                "role": "generation_plan_and_constraints",
                "requires_manual_aggregation": True,
                "use_action_brief_as_generation_plan": True,
                "treat_constraints_as_hard_limits": True,
                "do_not_copy_competitor_text": True,
                "do_not_treat_competitor_facts_as_own_product_facts": True,
            },
            "filters": {
                "brief_id": effective_brief_id,
                "fields": requested_fields,
                "purpose": purpose,
                "include_raw_copy": include_raw_copy,
            },
        }

    build_listing_agent_tools_brief_id = brief_id
    return [listing_rules_tool, competitor_analysis_tool]


def empty_action_brief() -> dict[str, Any]:
    return {
        "positioning": None,
        "title_plan": [],
        "bullet_plan": [],
        "description_plan": [],
        "keywords_to_use": [],
        "search_terms": [],
        "differentiators": [],
        "must_cover": [],
    }


def empty_constraints() -> dict[str, Any]:
    return {
        "avoid_terms": [],
        "avoid_claim_types": [],
        "do_not_infer": [],
        "requires_user_evidence": [],
        "competitor_copy_policy": "do_not_copy",
    }
