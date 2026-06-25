from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CompetitorImportItem(BaseModel):
    """Single competitor input item submitted by the user."""

    input_type: Literal["url", "asin"]
    input_value: str = Field(min_length=1)


class CompetitorImportRequest(BaseModel):
    """Request body for importing competitor URLs or ASINs."""

    conversation_id: str
    brief_id: str
    items: list[CompetitorImportItem] = Field(min_length=1)


class CompetitorInputResponse(BaseModel):
    """Persisted competitor input returned after import."""

    id: str
    conversation_id: str
    brief_id: str | None
    input_type: str
    input_value: str
    normalized_url: str | None
    asin: str | None
    status: str
    created_at: datetime


class CompetitorImportAnalysisJobResponse(BaseModel):
    """Queued analysis job created for one imported competitor input."""

    competitor_input_id: str
    job_id: str
    status: str


class CompetitorImportResponse(BaseModel):
    """Result of saving competitor inputs and queuing later analysis."""

    job_id: str
    status: str
    imported_count: int
    items: list[CompetitorInputResponse]
    analysis_jobs: list[CompetitorImportAnalysisJobResponse] = Field(default_factory=list)


class CompetitorSummaryResponse(BaseModel):
    """Structured competitor analysis result."""

    id: str
    competitor_input_id: str
    brief_id: str | None
    title: str | None
    bullets: list[str] | None
    description_text: str | None
    search_terms: list[str] | None
    feature_summary: list[str] | None
    keyword_summary: list[str] | None
    risk_summary: list[str] | None
    raw_content_snapshot: str | None
    extraction_result: dict | None = None
    analysis_result: dict | None = None
    created_at: datetime
    updated_at: datetime


class CompetitorAnalysisResponse(BaseModel):
    """Result returned after analyzing a competitor input."""

    job_id: str
    status: str
    competitor_input_id: str
    summary: CompetitorSummaryResponse | None = None
    error_message: str | None = None


class AggregatedCompetitorAnalysisResponse(BaseModel):
    """Aggregated competitor analysis report for one product Brief."""

    id: str
    brief_id: str
    conversation_id: str | None
    status: str
    competitor_count: int
    report: dict | None
    action_brief: dict | None
    constraints: dict | None
    error_message: str | None
    model_name: str | None
    created_at: datetime
    updated_at: datetime


class CompetitorAnalysisListResponse(BaseModel):
    """List response for read-only competitor analysis reports."""

    items: list[AggregatedCompetitorAnalysisResponse]
