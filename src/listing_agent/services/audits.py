import json
from typing import Any

from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import AuditResult, Draft, Rule
from listing_agent.services.llm import (
    get_chat_model_with_config,
    read_structured_response,
    record_model_invocation,
)


class AuditError(Exception):
    """Raised when a draft cannot be audited."""


class AuditFindingOutput(BaseModel):
    """Single structured audit finding returned by the LLM."""

    field: str = Field(min_length=1)
    severity: str = Field(min_length=1)
    message: str = Field(min_length=1)
    rule_id: str | None = None


class AuditOutput(BaseModel):
    """Structured LLM output contract for listing copy audit."""

    status: str = Field(pattern="^(pass|warning|fail)$")
    risk_score: int = Field(ge=0, le=100)
    findings: list[AuditFindingOutput] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class AuditService:
    """Audit generated listing copy against the active rule set."""

    async def audit_draft(
        self,
        session: AsyncSession,
        draft_id: str,
        api_endpoint: str = "POST /api/v1/audits/run",
    ) -> AuditResult:
        """Load a draft, audit it with active rules, and persist the result."""
        draft = await self._get_draft(session, draft_id)
        if not await self._has_active_rules(session):
            raise AuditError("no active listing rules are available")
        context = build_audit_context(draft)
        audited = await self._audit_copy(session, context, api_endpoint)
        validate_audit_output(audited)

        used_rule_ids = sorted(
            {
                finding.get("rule_id")
                for finding in audited["findings"]
                if isinstance(finding, dict) and finding.get("rule_id")
            }
        )
        audit = AuditResult(
            draft_id=draft.id,
            status=audited["status"],
            risk_score=audited["risk_score"],
            findings=audited["findings"],
            suggestions=audited["suggestions"],
            used_rule_ids=used_rule_ids,
        )
        session.add(audit)
        await session.flush()
        await self._advance_conversation(session, draft.conversation_id)
        await session.commit()
        await session.refresh(audit)
        return audit

    async def _get_draft(self, session: AsyncSession, draft_id: str) -> Draft:
        result = await session.execute(select(Draft).where(Draft.id == draft_id))
        draft = result.scalar_one_or_none()
        if draft is None:
            raise AuditError("draft not found")
        return draft

    async def _has_active_rules(self, session: AsyncSession) -> bool:
        result = await session.execute(
            select(Rule.id)
            .where(Rule.is_active.is_(True))
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def _audit_copy(
        self,
        session: AsyncSession,
        context: dict[str, Any],
        api_endpoint: str,
    ) -> dict[str, Any]:
        """Call the configured chat model and read its structured audit output."""
        model, model_config = await get_chat_model_with_config(session)
        agent = create_agent(
            model=model,
            tools=[],
            response_format=ProviderStrategy(schema=AuditOutput),
            system_prompt=(
                "You perform final quality control for Amazon US listing copy. "
                "policy_pack is the mandatory source of truth for this audit. "
                "policy_pack.field_rules contains the binding rules, not optional "
                "references. Rules with level hard are non-negotiable. "
                "Only check hard rule violations, fabricated product facts, high-risk "
                "claims, required output structure errors, and obvious competitor copy risk. "
                "Do not provide open-ended style improvements, generic SEO suggestions, "
                "or subjective wording polish. Reference rule_id for every finding that "
                "maps to a policy_pack rule. "
                "Return status only as pass, warning, or fail."
            ),
        )
        response = await agent.ainvoke(
            {
                "messages": [
                    HumanMessage(
                        content=(
                            "Final-audit this Amazon listing draft. Return a status, a 0-100 "
                            "risk score where higher means riskier, hard findings, and only "
                            "required risk-reduction suggestions.\nContext:\n"
                            f"{json.dumps(context, ensure_ascii=False)}"
                        )
                    )
                ]
            }
        )
        await record_model_invocation(
            session,
            model_config_id=model_config.id,
            feature_name="审核文案",
            api_endpoint=api_endpoint,
            response=response,
        )
        parsed = read_structured_response(
            response,
            schema=AuditOutput,
        )
        if parsed is not None:
            return parsed
        raise AuditError("LLM response did not include structured output")

    async def _advance_conversation(self, session: AsyncSession, conversation_id: str) -> None:
        result = await session.execute(
            select(Conversation).where(Conversation.id == conversation_id)
        )
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            conversation.current_step = "review_audit"


def build_audit_context(draft: Draft) -> dict[str, Any]:
    """Build the compact prompt context used for copy audit."""
    generation_context = (
        draft.generation_context
        if isinstance(draft.generation_context, dict)
        else {}
    )
    policy_pack = generation_context.get("policy_pack")
    if not isinstance(policy_pack, dict):
        raise AuditError("draft does not include policy_pack for audit")
    return {
        "draft": {
            "id": draft.id,
            "brief_id": draft.brief_id,
            "title": draft.title,
            "bullets": draft.bullets or [],
            "description_text": draft.description_text,
            "search_terms": draft.search_terms or [],
            "version_no": draft.version_no,
        },
        "policy_pack": policy_pack,
        "audit_requirements": {
            "status": "one of pass, warning, fail",
            "risk_score": "integer from 0 to 100; higher means riskier",
            "findings": "list of field, severity, message, and optional rule_id",
            "suggestions": (
                "only required changes for hard failures or high-risk warnings; no style polish"
            ),
            "scope": [
                "hard rule violation",
                "fabricated facts",
                "high-risk claims",
                "structure errors",
                "competitor copy risk",
            ],
        },
    }


def validate_audit_output(value: dict[str, Any]) -> None:
    """Validate the minimal audit contract before persisting."""
    if not isinstance(value, dict):
        raise AuditError("LLM response must be a JSON object")
    required = ("status", "risk_score", "findings", "suggestions")
    missing = [field for field in required if field not in value]
    if missing:
        raise AuditError(f"LLM response missing fields: {', '.join(missing)}")
    if value["status"] not in {"pass", "warning", "fail"}:
        raise AuditError("audit status must be one of: pass, warning, fail")
    if not isinstance(value["risk_score"], int) or not 0 <= value["risk_score"] <= 100:
        raise AuditError("audit risk_score must be an integer from 0 to 100")
    if not isinstance(value["findings"], list):
        raise AuditError("audit findings must be a list")
    for finding in value["findings"]:
        if not isinstance(finding, dict):
            raise AuditError("each audit finding must be an object")
        for field in ("field", "severity", "message"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise AuditError(f"each audit finding must include {field}")
    if not isinstance(value["suggestions"], list) or not all(
        isinstance(item, str) and item.strip() for item in value["suggestions"]
    ):
        raise AuditError("audit suggestions must be a list of strings")
