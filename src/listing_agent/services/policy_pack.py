from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.v1_data import CompetitorAnalysis, ProductBrief, Rule


def product_facts_from_brief(brief: ProductBrief) -> dict[str, Any]:
    """Return verified product facts that may be used as copy source of truth."""
    return {
        "product_name": brief.product_name,
        "brand": brief.brand,
        "category": brief.category,
        "marketplace": brief.marketplace,
        "language": brief.language,
        "core_features": brief.core_features or [],
        "materials": brief.materials or [],
        "color": brief.color,
        "quantity": brief.quantity,
        "size_info": brief.size_info,
        "target_audience": brief.target_audience,
        "keywords_seed": brief.keywords_seed or [],
    }


async def build_policy_pack(
    session: AsyncSession,
    brief: ProductBrief,
    custom_prompt: str | None = None,
) -> dict[str, Any]:
    """Build a structured generation policy from product facts, rules, and competitors."""
    rules = await _load_active_rules(session)
    competitor_analysis = await _load_competitor_analysis(session, brief.id)
    action_brief = (
        competitor_analysis.action_brief
        if competitor_analysis is not None and isinstance(competitor_analysis.action_brief, dict)
        else {}
    )
    constraints = (
        competitor_analysis.constraints
        if competitor_analysis is not None and isinstance(competitor_analysis.constraints, dict)
        else {}
    )
    missing_facts = _missing_facts(brief, constraints)
    avoid_terms = _dedupe_text(
        _flatten_text(constraints.get("avoid_terms"))
        + _flatten_text(constraints.get("avoid_claim_types"))
    )
    keywords_seed = _flatten_text(brief.keywords_seed)
    competitor_keywords = _flatten_text(action_brief.get("keywords_to_use")) + _flatten_text(
        action_brief.get("search_terms")
    )
    return {
        "product_facts": product_facts_from_brief(brief),
        "field_rules": _build_field_rules(rules),
        "keyword_plan": {
            "must_use": _dedupe_text(keywords_seed),
            "nice_to_have": _dedupe_text(competitor_keywords),
            "avoid": avoid_terms,
        },
        "claims_policy": {
            "allowed_claims": _flatten_text(brief.core_features),
            "forbidden_claims": avoid_terms,
            "requires_evidence": _dedupe_text(
                _flatten_text(constraints.get("requires_user_evidence"))
                + _flatten_text(constraints.get("do_not_infer"))
            ),
        },
        "competitor_strategy": {
            "positioning": action_brief.get("positioning"),
            "title_plan": _flatten_text(action_brief.get("title_plan")),
            "bullet_plan": _flatten_text(action_brief.get("bullet_plan")),
            "description_plan": _flatten_text(action_brief.get("description_plan")),
            "differentiators": _flatten_text(action_brief.get("differentiators")),
            "must_cover": _flatten_text(action_brief.get("must_cover")),
            "do_not_copy": True,
            "source_analysis_id": (
                competitor_analysis.id
                if competitor_analysis is not None
                else None
            ),
        },
        "missing_facts": missing_facts,
        "custom_prompt_policy": {
            "value": (
                custom_prompt.strip()
                if isinstance(custom_prompt, str) and custom_prompt.strip()
                else None
            ),
            "scope": "style, tone, selling point priority, and emphasis only",
            "cannot_override": [
                "product facts",
                "field rules",
                "output contract",
                "competitor constraints",
                "forbidden claims",
            ],
        },
        "output_contract": {
            "title": "one title",
            "bullets": "exactly five bullet points",
            "description_text": "description HTML following active description rules",
            "search_terms": "backend search terms as phrase list",
        },
    }


async def _load_active_rules(session: AsyncSession) -> list[Rule]:
    result = await session.execute(
        select(Rule)
        .where(Rule.is_active.is_(True))
        .order_by(Rule.priority, Rule.rule_category, Rule.created_at.desc())
    )
    return list(result.scalars().all())


async def _load_competitor_analysis(
    session: AsyncSession,
    brief_id: str,
) -> CompetitorAnalysis | None:
    result = await session.execute(
        select(CompetitorAnalysis).where(CompetitorAnalysis.brief_id == brief_id)
    )
    return result.scalar_one_or_none()


def _rule_prompt_payload(rule: Rule) -> dict[str, Any]:
    return {
        "content": rule.rule_content,
        "level": _normalized_level(rule.rule_level),
    }


def _build_field_rules(rules: list[Rule]) -> dict[str, list[dict[str, Any]]]:
    field_rules = {
        "global": [],
        "title": [],
        "bullets": [],
        "description_text": [],
        "search_terms": [],
        "competitor_usage": [],
        "output_contract": [],
    }
    aliases = {
        "global": "global",
        "title": "title",
        "bullet": "bullets",
        "bullets": "bullets",
        "description_text": "description_text",
        "description": "description_text",
        "search": "search_terms",
        "search_terms": "search_terms",
        "keyword": "search_terms",
        "competitor_usage": "competitor_usage",
        "competitor": "competitor_usage",
        "output_contract": "output_contract",
        "contract": "output_contract",
    }
    for rule in rules:
        target = _rule_target(rule, aliases)
        field_rules[target].append(_rule_prompt_payload(rule))
    return field_rules


def _rule_target(rule: Rule, aliases: dict[str, str]) -> str:
    category = (rule.rule_category or "").lower()
    return next((value for key, value in aliases.items() if key in category), "global")


def _normalized_level(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized == "reference":
        return "guideline"
    if normalized in {"hard", "soft", "guideline"}:
        return normalized
    return "guideline"


def _missing_facts(brief: ProductBrief, constraints: dict[str, Any]) -> list[str]:
    missing = []
    if not brief.materials:
        missing.append("materials")
    if not brief.size_info:
        missing.append("size_info")
    if not brief.target_audience:
        missing.append("target_audience")
    for value in _flatten_text(constraints.get("requires_user_evidence")):
        missing.append(value)
    for value in _flatten_text(constraints.get("do_not_infer")):
        missing.append(value)
    return _dedupe_text(missing)


def _flatten_text(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        flattened: list[str] = []
        for item in value:
            flattened.extend(_flatten_text(item))
        return flattened
    if isinstance(value, dict):
        return _flatten_text(list(value.values()))
    return [str(value).strip()] if str(value).strip() else []


def _dedupe_text(values: list[str]) -> list[str]:
    seen = set()
    result = []
    for value in values:
        cleaned = " ".join(str(value).split())
        normalized = cleaned.lower()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
    return result
