from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from listing_agent.core.time import now_app_timezone
from listing_agent.db.base import Base


def _app_now() -> datetime:
    """Return timezone-aware UTC+8 timestamps for persisted records."""
    return now_app_timezone()


def _prefixed_id(prefix: str) -> str:
    """Create readable public IDs for V1 records."""
    return f"{prefix}_{uuid4().hex}"


def new_brief_id() -> str:
    """Generate a product brief ID."""
    return _prefixed_id("brief")


def new_competitor_input_id() -> str:
    """Generate a competitor input ID."""
    return _prefixed_id("comp_in")


def new_competitor_summary_id() -> str:
    """Generate a competitor summary ID."""
    return _prefixed_id("comp_sum")


def new_competitor_analysis_id() -> str:
    """Generate an aggregated competitor analysis ID."""
    return _prefixed_id("comp_analysis")


def new_rule_id() -> str:
    """Generate a structured rule ID."""
    return _prefixed_id("rule")


def new_draft_id() -> str:
    """Generate a draft ID."""
    return _prefixed_id("draft")


def new_audit_id() -> str:
    """Generate an audit result ID."""
    return _prefixed_id("audit")


def new_job_id() -> str:
    """Generate an async job ID."""
    return _prefixed_id("job")


def new_model_config_id() -> str:
    """Generate a model configuration ID."""
    return _prefixed_id("model")


def new_model_invocation_log_id() -> str:
    """Generate a model invocation log ID."""
    return _prefixed_id("model_log")


class ModelConfig(Base):
    """LLM model configuration managed from the admin UI."""

    __tablename__ = "model_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_model_config_id)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="openai")
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    api_key: Mapped[str] = mapped_column(Text, nullable=False)
    base_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thinking_config: Mapped[str] = mapped_column(String(32), nullable=False, default="disabled")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )


class ModelInvocationLog(Base):
    """Token usage and call metadata for one model invocation."""

    __tablename__ = "model_invocation_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_model_invocation_log_id)
    model_config_id: Mapped[str] = mapped_column(
        ForeignKey("model_configs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    api_endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now, index=True)


class ProductBrief(Base):
    """Structured product information collected from a conversation."""

    __tablename__ = "product_briefs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_brief_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    brand: Mapped[str | None] = mapped_column(String(255), nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    marketplace: Mapped[str] = mapped_column(String(16), nullable=False, default="US")
    language: Mapped[str] = mapped_column(String(32), nullable=False, default="en-US")
    core_features: Mapped[list | None] = mapped_column(JSON, nullable=True)
    materials: Mapped[list | None] = mapped_column(JSON, nullable=True)
    color: Mapped[str | None] = mapped_column(String(255), nullable=True)
    quantity: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    target_audience: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords_seed: Mapped[list | None] = mapped_column(JSON, nullable=True)
    completeness_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )

    competitor_inputs: Mapped[list["CompetitorInput"]] = relationship(back_populates="brief")
    drafts: Mapped[list["Draft"]] = relationship(back_populates="brief")


class CompetitorInput(Base):
    """Raw competitor URL or ASIN submitted by the user."""

    __tablename__ = "competitor_inputs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_competitor_input_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_briefs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    input_type: Mapped[str] = mapped_column(String(32), nullable=False)
    input_value: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    asin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)

    brief: Mapped[ProductBrief | None] = relationship(back_populates="competitor_inputs")
    summary: Mapped["CompetitorSummary | None"] = relationship(back_populates="competitor_input")


class CompetitorSummary(Base):
    """Structured competitor analysis result."""

    __tablename__ = "competitor_summaries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_competitor_summary_id)
    competitor_input_id: Mapped[str] = mapped_column(
        ForeignKey("competitor_inputs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_briefs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_terms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    feature_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    keyword_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    risk_summary: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    raw_content_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    extraction_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    analysis_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )

    competitor_input: Mapped[CompetitorInput] = relationship(back_populates="summary")


class CompetitorAnalysis(Base):
    """Aggregated read-only competitor analysis report for one product Brief."""

    __tablename__ = "competitor_analyses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_competitor_analysis_id)
    brief_id: Mapped[str] = mapped_column(
        ForeignKey("product_briefs.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    conversation_id: Mapped[str | None] = mapped_column(
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="completed", index=True)
    competitor_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    action_brief: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    constraints: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )


class Rule(Base):
    """Manually maintained Amazon listing rule."""

    __tablename__ = "rules"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_rule_id)
    rule_category: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    rule_title: Mapped[str] = mapped_column(String(255), nullable=False)
    rule_content: Mapped[str] = mapped_column(Text, nullable=False)
    rule_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rule_scope: Mapped[str] = mapped_column(String(128), nullable=False, default="amazon_listing")
    rule_level: Mapped[str] = mapped_column(String(32), nullable=False, default="guideline")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    source_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_app_now,
        onupdate=_app_now,
    )


class Draft(Base):
    """A generated listing copy draft."""

    __tablename__ = "drafts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_draft_id)
    conversation_id: Mapped[str] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    brief_id: Mapped[str | None] = mapped_column(
        ForeignKey("product_briefs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullets: Mapped[list | None] = mapped_column(JSON, nullable=True)
    description_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    search_terms: Mapped[list | None] = mapped_column(JSON, nullable=True)
    generation_context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)

    brief: Mapped[ProductBrief | None] = relationship(back_populates="drafts")
    audit_results: Mapped[list["AuditResult"]] = relationship(back_populates="draft")


class AuditResult(Base):
    """Rule and risk audit result for a draft."""

    __tablename__ = "audit_results"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_audit_id)
    draft_id: Mapped[str] = mapped_column(
        ForeignKey("drafts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    risk_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    findings: Mapped[list | None] = mapped_column(JSON, nullable=True)
    suggestions: Mapped[list | None] = mapped_column(JSON, nullable=True)
    used_rule_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)

    draft: Mapped[Draft] = relationship(back_populates="audit_results")


class Job(Base):
    """A lightweight async task record."""

    __tablename__ = "jobs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=new_job_id)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    related_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued", index=True)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_app_now)

