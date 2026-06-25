import json
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import (
    AuditResult,
    Draft,
    ProductBrief,
    Rule,
)
from listing_agent.services.agent_tools import build_listing_agent_tools
from listing_agent.services.briefs import get_missing_required_fields
from listing_agent.services.copy_validator import validate_against_policy_pack
from listing_agent.services.llm import (
    get_chat_model_with_config,
    read_structured_response,
    record_model_invocation,
)
from listing_agent.services.policy_pack import build_policy_pack


class DraftGenerationError(Exception):
    """Raised when listing copy cannot be generated from the current context."""


class ComplianceTraceOutput(BaseModel):
    """Trace how the generation complied with the supplied policy pack."""

    used_rule_ids: list[str] = Field(default_factory=list)
    applied_constraints: list[str] = Field(default_factory=list)
    avoided_terms: list[str] = Field(default_factory=list)
    missing_facts_handling: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


class ListingCopyOutput(BaseModel):
    """Structured LLM output contract for generated Amazon listing copy."""

    title: str = Field(min_length=1)
    bullets: list[str] = Field(min_length=5, max_length=5)
    description_text: str = Field(min_length=1)
    search_terms: list[str] = Field(default_factory=list)
    compliance_trace: ComplianceTraceOutput = Field(default_factory=ComplianceTraceOutput)


class ListingRewriteOutput(ListingCopyOutput):
    """Structured LLM output contract for rewritten Amazon listing copy."""

    change_summary: list[str] = Field(default_factory=list)


LONG_DESCRIPTION_HTML_REQUIREMENTS = (
    "The description_text field must be the long description content, not a short "
    "product description paragraph. Return description_text as HTML only, using exactly "
    "this structure: "
    "<p>[Description title: one concise line, core selling point, Title Case, no extra line break]</p> "
    "<p><b>SPECIFICATION:</b></p> "
    "<p>Brand: </p> "
    "<p>Name: </p> "
    "<p>Color: </p> "
    "<p>Material: </p> "
    "<p><b>SIZE:</b> </p> "
    "<p>Applicable: </p> "
    "<p><b>FEATURES:</b></p> "
    "<p>Feature 1</p> "
    "<p>Feature 2</p> "
    "<p>Feature 3</p>. "
    "Fill values from verified brief facts only. Leave a value blank after the colon "
    "if the fact is unavailable. Put each feature in its own <p> line. Do not use "
    "Markdown, bullet characters, extra wrappers, tables, scripts, styles, or claims "
    "not supported by the brief."
)


class DraftService:
    """Generate and persist Amazon listing copy drafts."""

    async def generate_draft(
        self,
        session: AsyncSession,
        brief_id: str,
        custom_prompt: str | None = None,
    ) -> Draft:
        """Load context, call the configured chat model, and save a draft."""
        brief = await self._get_brief(session, brief_id)
        missing_fields = get_missing_required_fields(brief)
        if missing_fields:
            raise DraftGenerationError(
                f"brief is missing required fields: {', '.join(missing_fields)}"
            )

        if not await self._has_active_rules(session):
            raise DraftGenerationError("no active listing rules are available")
        policy_pack = await build_policy_pack(session, brief, custom_prompt)
        prompt_context = build_generation_context(
            brief,
            policy_pack=policy_pack,
            custom_prompt=custom_prompt,
        )
        generated = await self._generate_copy(session, prompt_context)
        validation_result = validate_against_policy_pack(generated, policy_pack)
        repaired = False
        if not validation_result.passed:
            generated = await self._repair_copy(
                session,
                context=prompt_context,
                draft=generated,
                validator_errors=validation_result.to_dict()["errors"],
            )
            repaired = True
            validation_result = validate_against_policy_pack(generated, policy_pack)
        if validation_result.normalized_draft is not None:
            generated = {
                **generated,
                **validation_result.normalized_draft,
            }
        if not validation_result.passed:
            raise DraftGenerationError(
                "generated draft failed policy validation: "
                + json.dumps(validation_result.to_dict()["errors"], ensure_ascii=False)
            )
        validate_generated_copy(generated)

        version_no = await self._next_version_no(session, brief.id)
        draft = Draft(
            conversation_id=brief.conversation_id,
            brief_id=brief.id,
            title=generated["title"],
            bullets=generated["bullets"],
            description_text=generated["description_text"],
            search_terms=generated["search_terms"],
            generation_context=summarize_generation_context(
                prompt_context,
                generated,
                validation_result.to_dict(),
                repaired,
            ),
            version_no=version_no,
        )
        session.add(draft)
        await session.flush()
        await self._advance_conversation(session, brief.conversation_id, draft.id)
        await session.commit()
        await session.refresh(draft)
        return draft

    async def rewrite_draft(
        self,
        session: AsyncSession,
        draft_id: str,
        instructions: str,
    ) -> Draft:
        """Rewrite an existing draft using the latest audit result and save a new version."""
        original_draft = await self._get_draft(session, draft_id)
        latest_audit = await self._get_latest_audit(session, draft_id)
        if not await self._has_active_rules(session):
            raise DraftGenerationError("no active listing rules are available")
        prompt_context = build_rewrite_context(
            original_draft=original_draft,
            latest_audit=latest_audit,
            instructions=instructions,
        )
        rewritten = await self._rewrite_copy(session, prompt_context)
        validate_rewritten_copy(rewritten)

        if original_draft.brief_id is not None:
            version_no = await self._next_version_no(session, original_draft.brief_id)
        else:
            version_no = original_draft.version_no + 1

        draft = Draft(
            conversation_id=original_draft.conversation_id,
            brief_id=original_draft.brief_id,
            title=rewritten["title"],
            bullets=rewritten["bullets"],
            description_text=rewritten["description_text"],
            search_terms=rewritten["search_terms"],
            generation_context=summarize_rewrite_context(prompt_context, rewritten),
            version_no=version_no,
        )
        session.add(draft)
        await session.flush()
        await self._advance_conversation(session, original_draft.conversation_id, draft.id)
        await session.commit()
        await session.refresh(draft)
        return draft

    async def _get_brief(self, session: AsyncSession, brief_id: str) -> ProductBrief:
        result = await session.execute(select(ProductBrief).where(ProductBrief.id == brief_id))
        brief = result.scalar_one_or_none()
        if brief is None:
            raise DraftGenerationError("brief not found")
        return brief

    async def _get_draft(self, session: AsyncSession, draft_id: str) -> Draft:
        result = await session.execute(select(Draft).where(Draft.id == draft_id))
        draft = result.scalar_one_or_none()
        if draft is None:
            raise DraftGenerationError("draft not found")
        return draft

    async def _get_latest_audit(
        self,
        session: AsyncSession,
        draft_id: str,
    ) -> AuditResult | None:
        result = await session.execute(
            select(AuditResult)
            .where(AuditResult.draft_id == draft_id)
            .order_by(AuditResult.created_at.desc())
        )
        return result.scalars().first()

    async def _has_active_rules(self, session: AsyncSession) -> bool:
        result = await session.execute(
            select(Rule.id)
            .where(Rule.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _generate_copy(
        self,
        session: AsyncSession,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the configured chat model and read its structured output."""
        model, model_config = await get_chat_model_with_config(session)
        agent = create_agent(
            model=model,
            tools=build_listing_agent_tools(session, brief_id=context["brief"]["id"]),
            response_format=ProviderStrategy(schema=ListingCopyOutput),
            system_prompt=(
                "You generate compliant Amazon listing copy for the US marketplace. "
                "policy_pack is the source of truth and has already compiled product facts, "
                "active rules, competitor strategy, missing facts, and forbidden terms. "
                "Hard rules and forbidden claims are non-negotiable. Competitor strategy "
                "is guidance only and must not become product facts. Use listing_rules_tool "
                "and competitor_analysis_tool only to cross-check policy_pack if needed; "
                "never override policy_pack with tool output. user_custom_prompt can affect "
                "tone and emphasis only. Include compliance_trace with used rule IDs, applied "
                "constraints, avoided terms, missing-fact handling, and assumptions. "
                f"{LONG_DESCRIPTION_HTML_REQUIREMENTS} "
                "Return the final listing copy as structured output."
            ),
        )
        response = await agent.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "Generate Amazon listing copy under policy_pack. Produce one title, "
                            "exactly five bullet points, one long description HTML, backend "
                            "Search Terms, and compliance_trace.\nContext:\n"
                            f"{json.dumps(context, ensure_ascii=False)}"
                        )
                    )
                ]
            }
        )
        await record_model_invocation(
            session,
            model_config_id=model_config.id,
            feature_name="生成文案",
            api_endpoint="POST /api/v1/drafts/generate",
            response=response,
        )
        parsed = read_structured_response(
            response,
            schema=ListingCopyOutput,
        )
        if parsed is not None:
            return parsed
        raise DraftGenerationError("LLM response did not include structured output")

    async def _rewrite_copy(
        self,
        session: AsyncSession,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Call the configured chat model and read its structured rewrite output."""
        model, model_config = await get_chat_model_with_config(session)
        agent = create_agent(
            model=model,
            tools=[
                *build_listing_agent_tools(
                    session,
                    brief_id=context["original_draft"].get("brief_id"),
                ),
            ],
            response_format=ProviderStrategy(schema=ListingRewriteOutput),
            system_prompt=(
                "You rewrite Amazon US listing copy from an existing draft. "
                "Use listing_rules_tool and competitor_analysis_tool as needed. "
                "Treat competitor_analysis_tool output as strategy input only. Preserve "
                "product facts, avoid risky competitor claims, and avoid inventing claims. "
                f"{LONG_DESCRIPTION_HTML_REQUIREMENTS} "
                "Return the final rewrite as structured output."
            ),
        )
        response = await agent.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "Rewrite this Amazon listing draft from the context.\nContext:\n"
                            f"{json.dumps(context, ensure_ascii=False)}"
                        )
                    )
                ]
            }
        )
        await record_model_invocation(
            session,
            model_config_id=model_config.id,
            feature_name="改写文案",
            api_endpoint="POST /api/v1/drafts/{draft_id}/rewrite",
            response=response,
        )
        parsed = read_structured_response(
            response,
            schema=ListingRewriteOutput,
        )
        if parsed is not None:
            return parsed
        raise DraftGenerationError("LLM response did not include structured output")

    async def _repair_copy(
        self,
        session: AsyncSession,
        context: dict[str, Any],
        draft: dict[str, Any],
        validator_errors: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Repair only deterministic validator failures once."""
        model, model_config = await get_chat_model_with_config(session)
        agent = create_agent(
            model=model,
            tools=[],
            response_format=ProviderStrategy(schema=ListingCopyOutput),
            system_prompt=(
                "You repair Amazon US listing copy. Only fix the exact fields and "
                "issues listed in validator_errors. Do not add product facts, do not "
                "change overall positioning, do not copy competitor wording, and do "
                "not rewrite unrelated fields. policy_pack remains the source of truth. "
                f"{LONG_DESCRIPTION_HTML_REQUIREMENTS} "
                "Return the full repaired listing copy as structured output."
            ),
        )
        repair_context = {
            "policy_pack": context["policy_pack"],
            "draft": draft,
            "validator_errors": validator_errors,
        }
        response = await agent.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "Repair this listing draft only for validator_errors.\nContext:\n"
                            f"{json.dumps(repair_context, ensure_ascii=False)}"
                        )
                    )
                ]
            }
        )
        await record_model_invocation(
            session,
            model_config_id=model_config.id,
            feature_name="repair_copy",
            api_endpoint="POST /api/v1/drafts/generate",
            response=response,
        )
        parsed = read_structured_response(response, schema=ListingCopyOutput)
        if parsed is not None:
            return parsed
        raise DraftGenerationError("LLM repair response did not include structured output")

    async def _next_version_no(self, session: AsyncSession, brief_id: str) -> int:
        result = await session.execute(
            select(func.max(Draft.version_no)).where(Draft.brief_id == brief_id)
        )
        current = result.scalar_one_or_none() or 0
        return current + 1

    async def _advance_conversation(
        self,
        session: AsyncSession,
        conversation_id: str,
        draft_id: str,
    ) -> None:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            conversation.active_draft_id = draft_id
            conversation.current_step = "audit_draft"


def build_generation_context(
    brief: ProductBrief,
    policy_pack: dict[str, Any],
    custom_prompt: str | None = None,
) -> dict[str, Any]:
    """Build the compact prompt context used for copy generation."""
    cleaned_custom_prompt = custom_prompt.strip() if isinstance(custom_prompt, str) else ""
    return {
        "brief": {
            "id": brief.id,
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
        },
        "policy_pack": policy_pack,
        "user_custom_prompt": cleaned_custom_prompt or None,
        "available_tools": ["listing_rules_tool", "competitor_analysis_tool"],
        "output_requirements": {
            "title": "one Amazon title",
            "bullets": "exactly five bullet points",
            "description_text": (
                "long description HTML with <p> lines for title, SPECIFICATION, SIZE, "
                "Applicable, and FEATURES"
            ),
            "search_terms": "backend Search Terms as a list of phrases",
        },
    }


def summarize_generation_context(
    context: dict[str, Any],
    generated: dict[str, Any],
    validation_result: dict[str, Any],
    repaired: bool,
) -> dict[str, Any]:
    """Persist traceable but compact context metadata with each draft."""
    return {
        "brief": context["brief"],
        "policy_pack": context["policy_pack"],
        "user_custom_prompt": context.get("user_custom_prompt"),
        "available_tools": context["available_tools"],
        "compliance_trace": generated.get("compliance_trace", {}),
        "deterministic_validation": validation_result,
        "auto_repair": {
            "attempted": repaired,
            "max_attempts": 1,
        },
    }


def build_rewrite_context(
    original_draft: Draft,
    latest_audit: AuditResult | None,
    instructions: str,
) -> dict[str, Any]:
    """Build the compact prompt context used for copy rewrite."""
    findings = latest_audit.findings if latest_audit is not None else []
    suggestions = latest_audit.suggestions if latest_audit is not None else []
    return {
        "original_draft": {
            "id": original_draft.id,
            "brief_id": original_draft.brief_id,
            "title": original_draft.title,
            "bullets": original_draft.bullets or [],
            "description_text": original_draft.description_text,
            "search_terms": original_draft.search_terms or [],
            "version_no": original_draft.version_no,
            "generation_context": original_draft.generation_context or {},
        },
        "latest_audit": {
            "id": latest_audit.id if latest_audit is not None else None,
            "status": latest_audit.status if latest_audit is not None else None,
            "risk_score": latest_audit.risk_score if latest_audit is not None else None,
            "findings": findings or [],
            "suggestions": suggestions or [],
        },
        "available_tools": ["listing_rules_tool", "competitor_analysis_tool"],
        "user_instructions": instructions,
        "rewrite_requirements": {
            "preserve_facts": (
                "Do not invent dimensions, certifications, materials, or warranty terms."
            ),
            "scope": (
                "Prefer targeted edits that address audit findings unless instructed otherwise."
            ),
            "output": (
                "Return full title, five bullets, description_text as long description "
                "HTML, search_terms, and change_summary."
            ),
        },
    }


def summarize_rewrite_context(
    context: dict[str, Any],
    rewritten: dict[str, Any],
) -> dict[str, Any]:
    """Persist compact trace metadata for a rewritten draft."""
    latest_audit = context["latest_audit"]
    return {
        "rewrite": {
            "source_draft_id": context["original_draft"]["id"],
            "source_version_no": context["original_draft"]["version_no"],
            "source_audit_id": latest_audit["id"],
            "source_risk_score": latest_audit["risk_score"],
            "instructions": context["user_instructions"],
            "change_summary": rewritten.get("change_summary", []),
        },
        "available_tools": context["available_tools"],
    }


def validate_generated_copy(value: dict[str, Any]) -> None:
    """Validate the minimal draft contract before persisting."""
    if not isinstance(value, dict):
        raise DraftGenerationError("LLM response must be a JSON object")
    required = ("title", "bullets", "description_text", "search_terms")
    missing = [field for field in required if field not in value]
    if missing:
        raise DraftGenerationError(f"LLM response missing fields: {', '.join(missing)}")
    if not isinstance(value["title"], str) or not value["title"].strip():
        raise DraftGenerationError("generated title is empty")
    if not _is_text_list(value["bullets"]) or len(value["bullets"]) != 5:
        raise DraftGenerationError("generated bullets must contain exactly five strings")
    if not isinstance(value["description_text"], str) or not value["description_text"].strip():
        raise DraftGenerationError("generated description_text is empty")
    if not _looks_like_long_description_html(value["description_text"]):
        raise DraftGenerationError("generated description_text must be long description HTML")
    if not _is_text_list(value["search_terms"]):
        raise DraftGenerationError("generated search_terms must be a list of strings")


def validate_rewritten_copy(value: dict[str, Any]) -> None:
    """Validate the rewrite contract before persisting the new draft."""
    validate_generated_copy(value)
    if "change_summary" not in value:
        raise DraftGenerationError("LLM response missing fields: change_summary")
    if not _is_text_list(value["change_summary"]):
        raise DraftGenerationError("generated change_summary must be a list of strings")


def _is_text_list(value: Any) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) and item.strip() for item in value)


def _looks_like_long_description_html(value: str) -> bool:
    normalized = value.strip().lower()
    required_fragments = (
        "<p>",
        "</p>",
        "<b>specification:</b>",
        "<b>size:</b>",
        "<b>features:</b>",
    )
    return all(fragment in normalized for fragment in required_fragments)
