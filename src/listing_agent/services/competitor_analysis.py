import json
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.core.config import get_settings
from listing_agent.core.time import now_app_timezone
from listing_agent.models.conversation import Conversation
from listing_agent.models.v1_data import (
    CompetitorAnalysis,
    CompetitorInput,
    CompetitorSummary,
    Job,
    ProductBrief,
)
from listing_agent.services.llm import get_chat_model_with_config, record_model_invocation

COMPETITOR_SNAPSHOT_DIR = get_settings().resolved_app_data_dir / "competitor_snapshots"
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
        "image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
}
COMMON_WORDS = {
    "and",
    "for",
    "the",
    "with",
    "from",
    "this",
    "that",
    "your",
    "you",
    "are",
    "our",
    "not",
    "all",
    "into",
    "more",
    "product",
    "amazon",
}
RISK_TERMS = [
    "best",
    "guaranteed",
    "cure",
    "treat",
    "medical",
    "free shipping",
    "number one",
    "#1",
]


@dataclass(slots=True)
class CompetitorPage:
    """Fetched competitor page content."""

    status_code: int | None
    html: str | None
    error: str | None = None


@dataclass(slots=True)
class ExtractedCompetitorContent:
    """Public listing content extracted from a competitor page."""

    title: str | None
    bullets: list[str]
    description_text: str | None
    raw_text: str


class SingleCompetitorKeywordAnalysisOutput(BaseModel):
    """Required keyword-analysis section for one competitor."""

    primary: list[str] = Field(default_factory=list)
    long_tail: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)
    audiences: list[str] = Field(default_factory=list)
    risk_terms: list[str] = Field(default_factory=list)


class SingleCompetitorPositioningOutput(BaseModel):
    """Required positioning section for one competitor."""

    target_audience: list[str] = Field(default_factory=list)
    use_scenarios: list[str] = Field(default_factory=list)
    pain_points: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    tone: str | None = None


class SingleCompetitorContentPatternsOutput(BaseModel):
    """Required content-pattern section for one competitor."""

    title_pattern: str | None = None
    bullet_pattern: str | None = None
    information_density: str | None = None


class SingleCompetitorAnalysisOutput(BaseModel):
    """LLM-generated analysis for one competitor listing."""

    source: dict[str, Any] = Field(default_factory=dict)
    product_facts: dict[str, Any] = Field(default_factory=dict)
    selling_points: list[str] = Field(default_factory=list)
    keyword_analysis: SingleCompetitorKeywordAnalysisOutput = Field(
        default_factory=SingleCompetitorKeywordAnalysisOutput
    )
    positioning: SingleCompetitorPositioningOutput = Field(
        default_factory=SingleCompetitorPositioningOutput
    )
    content_patterns: SingleCompetitorContentPatternsOutput = Field(
        default_factory=SingleCompetitorContentPatternsOutput
    )
    risk_notes: list[str] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class MarketPatternsOutput(BaseModel):
    """Required market-pattern section for final competitor analysis."""

    common_features: list[str] = Field(default_factory=list)
    common_benefits: list[str] = Field(default_factory=list)
    common_scenarios: list[str] = Field(default_factory=list)
    common_audiences: list[str] = Field(default_factory=list)
    common_keywords: list[str] = Field(default_factory=list)
    common_title_patterns: list[str] = Field(default_factory=list)
    common_bullet_patterns: list[str] = Field(default_factory=list)


class CompetitorComparisonRowOutput(BaseModel):
    """One row in the competitor comparison matrix."""

    competitor_input_id: str | None = None
    title: str | None = None
    features: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    risk_terms: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    scenarios: list[str] = Field(default_factory=list)


class KeywordInsightsOutput(BaseModel):
    """Required keyword-analysis section for final competitor analysis."""

    primary: list[str] = Field(default_factory=list)
    long_tail: list[str] = Field(default_factory=list)
    attributes: list[str] = Field(default_factory=list)
    risk_terms: list[str] = Field(default_factory=list)


class RecommendedListingStrategyOutput(BaseModel):
    """Required Listing generation strategy section."""

    positioning: str | None = None
    title_strategy: list[str] = Field(default_factory=list)
    bullet_strategy: list[str] = Field(default_factory=list)
    description_strategy: list[str] = Field(default_factory=list)
    keyword_strategy: list[str] = Field(default_factory=list)
    avoid_strategy: list[str] = Field(default_factory=list)


class AggregatedCompetitorAnalysisOutput(BaseModel):
    """LLM-generated final competitor analysis report for one Brief."""

    brief: dict[str, Any] = Field(default_factory=dict)
    competitor_count: int = 0
    market_patterns: MarketPatternsOutput = Field(default_factory=MarketPatternsOutput)
    comparison_matrix: list[CompetitorComparisonRowOutput] = Field(default_factory=list)
    keyword_insights: KeywordInsightsOutput = Field(default_factory=KeywordInsightsOutput)
    differentiation_opportunities: list[str] = Field(default_factory=list)
    risk_summary: list[str] = Field(default_factory=list)
    recommended_listing_strategy: RecommendedListingStrategyOutput = Field(
        default_factory=RecommendedListingStrategyOutput
    )
    missing_user_facts: list[str] = Field(default_factory=list)


class CompetitorActionBriefOutput(BaseModel):
    """Compact generation plan for listing agents."""

    positioning: str | None = None
    title_plan: list[str] = Field(default_factory=list)
    bullet_plan: list[str] = Field(default_factory=list)
    description_plan: list[str] = Field(default_factory=list)
    keywords_to_use: list[str] = Field(default_factory=list)
    search_terms: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    must_cover: list[str] = Field(default_factory=list)


class CompetitorConstraintsOutput(BaseModel):
    """Hard constraints derived from competitor analysis."""

    avoid_terms: list[str] = Field(default_factory=list)
    avoid_claim_types: list[str] = Field(default_factory=list)
    do_not_infer: list[str] = Field(default_factory=list)
    requires_user_evidence: list[str] = Field(default_factory=list)
    competitor_copy_policy: str = "do_not_copy"


class CompetitorAnalysisPackageOutput(BaseModel):
    """Final stored aggregate analysis package."""

    report: AggregatedCompetitorAnalysisOutput = Field(default_factory=AggregatedCompetitorAnalysisOutput)
    action_brief: CompetitorActionBriefOutput = Field(default_factory=CompetitorActionBriefOutput)
    constraints: CompetitorConstraintsOutput = Field(default_factory=CompetitorConstraintsOutput)


class CompetitorInputNotFoundError(Exception):
    """Raised when a competitor input ID does not exist."""


class CompetitorAnalysisLLMError(Exception):
    """Raised when LLM competitor analysis cannot produce structured output."""


class CompetitorAggregationError(Exception):
    """Raised when final aggregated competitor analysis cannot be generated."""


class CompetitorAnalysisService:
    """Fetch competitor pages and persist structured analysis summaries."""

    async def analyze_competitor(
        self,
        session: AsyncSession,
        competitor_input_id: str,
        job: Job | None = None,
    ) -> tuple[Job, CompetitorSummary | None]:
        """Analyze one saved competitor input."""
        competitor_input = await self._get_competitor_input(session, competitor_input_id)
        job = await self._ensure_running_job(session, competitor_input, job)

        page_url = competitor_input.normalized_url
        if not page_url:
            return await self._mark_failed(
                session,
                job,
                competitor_input,
                "competitor url is missing",
            )

        page = await self._fetch_listing_page(page_url, competitor_input.asin)
        if page.error or not page.html:
            return await self._mark_failed(
                session,
                job,
                competitor_input,
                page.error or "empty page",
            )

        snapshot_path = write_competitor_snapshot(competitor_input.id, page.html)
        extracted = extract_competitor_content(page.html)
        if not has_extractable_competitor_content(extracted):
            return await self._mark_failed(
                session,
                job,
                competitor_input,
                "no extractable competitor listing content found",
            )
        try:
            summary = await self._upsert_summary(session, competitor_input, extracted, snapshot_path)
        except CompetitorAnalysisLLMError as exc:
            return await self._mark_failed(session, job, competitor_input, str(exc))

        competitor_input.status = "completed"
        job.status = "completed"
        job.finished_at = now_app_timezone()
        job.error_message = None
        job.result_summary = "Competitor analysis completed."
        await self._advance_conversation(session, competitor_input.conversation_id)
        await session.commit()
        await session.refresh(job)
        await session.refresh(summary)
        return job, summary

    async def _ensure_running_job(
        self,
        session: AsyncSession,
        competitor_input: CompetitorInput,
        job: Job | None,
    ) -> Job:
        """Create a job when called directly, or mark an existing queued job as running."""
        if job is None:
            job = Job(
                job_type="competitor_analysis",
                related_id=competitor_input.id,
                status="running",
                payload={"competitor_input_id": competitor_input.id},
                started_at=now_app_timezone(),
            )
            session.add(job)
            await session.flush()
            return job

        job.status = "running"
        job.started_at = job.started_at or now_app_timezone()
        job.payload = {
            **dict(job.payload or {}),
            "competitor_input_id": competitor_input.id,
        }
        await session.flush()
        return job

    async def _get_competitor_input(
        self,
        session: AsyncSession,
        competitor_input_id: str,
    ) -> CompetitorInput:
        """Load one competitor input by ID."""
        result = await session.execute(
            select(CompetitorInput).where(CompetitorInput.id == competitor_input_id)
        )
        competitor_input = result.scalar_one_or_none()
        if competitor_input is None:
            raise CompetitorInputNotFoundError(competitor_input_id)
        return competitor_input

    async def _fetch_page(self, url: str) -> CompetitorPage:
        """Fetch a competitor page and convert network failures into result data."""
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            return await self._fetch_page_with_client(client, url)

    async def _fetch_listing_page(self, url: str, asin: str | None) -> CompetitorPage:
        """Try multiple Amazon detail URLs and keep the first page with listing content."""
        last_page: CompetitorPage | None = None
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
            for candidate_url in build_fetch_urls(url, asin):
                page = await self._fetch_page_with_client(client, candidate_url)
                last_page = page
                if page.error or not page.html:
                    continue
                extracted = extract_competitor_content(page.html)
                if has_extractable_competitor_content(extracted):
                    return page
        return last_page or CompetitorPage(status_code=None, html=None, error="empty page")

    async def _fetch_page_with_client(self, client: httpx.AsyncClient, url: str) -> CompetitorPage:
        """Fetch a competitor page with an injected client for testability."""
        try:
            response = await client.get(url, headers=REQUEST_HEADERS)
            if is_amazon_continue_page(response.text):
                response = await submit_amazon_continue_form(client, response)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            response = getattr(exc, "response", None)
            status_code = response.status_code if response is not None else None
            return CompetitorPage(status_code=status_code, html=None, error=str(exc))
        return CompetitorPage(status_code=response.status_code, html=response.text)

    async def _upsert_summary(
        self,
        session: AsyncSession,
        competitor_input: CompetitorInput,
        extracted: ExtractedCompetitorContent,
        snapshot_path: str,
    ) -> CompetitorSummary:
        """Create or update a structured competitor summary."""
        result = await session.execute(
            select(CompetitorSummary).where(
                CompetitorSummary.competitor_input_id == competitor_input.id
            )
        )
        summary = result.scalar_one_or_none()
        keywords = build_keyword_summary(extracted)
        extraction_result = build_extraction_result(extracted, keywords, snapshot_path)
        heuristic_seed = build_single_competitor_analysis(
            competitor_input,
            extracted,
            keywords,
            snapshot_path,
        )
        analysis_result = await self._generate_single_competitor_analysis(
            session=session,
            competitor_input=competitor_input,
            extraction_result=extraction_result,
            heuristic_seed=heuristic_seed,
        )
        values = {
            "brief_id": competitor_input.brief_id,
            "title": extracted.title,
            "bullets": extracted.bullets,
            "description_text": extracted.description_text,
            "search_terms": keywords[:12],
            "feature_summary": build_feature_summary(extracted),
            "keyword_summary": keywords,
            "risk_summary": build_risk_summary(extracted),
            "raw_content_snapshot": snapshot_path,
            "extraction_result": extraction_result,
            "analysis_result": analysis_result,
        }
        if summary is None:
            summary = CompetitorSummary(
                competitor_input_id=competitor_input.id,
                **values,
            )
            session.add(summary)
        else:
            for key, value in values.items():
                setattr(summary, key, value)
        await session.flush()
        return summary

    async def _generate_single_competitor_analysis(
        self,
        *,
        session: AsyncSession,
        competitor_input: CompetitorInput,
        extraction_result: dict[str, Any],
        heuristic_seed: dict[str, Any],
    ) -> dict[str, Any]:
        """Use the configured LLM to produce one competitor analysis result."""
        context = {
            "competitor_input_id": competitor_input.id,
            "extraction_result": extraction_result,
            "heuristic_seed": heuristic_seed,
        }
        try:
            model, model_config = await get_chat_model_with_config(session)
            agent = create_agent(
                model=model,
                tools=[],
                response_format=SingleCompetitorAnalysisOutput,
                system_prompt=(
                    "You analyze one public Amazon competitor listing. Use only the "
                    "provided extraction and heuristic seed. Separate facts from inferred "
                    "strategy. Do not invent product facts. Do not copy competitor wording "
                    "as recommendations. Return a concise structured analysis with source, "
                    "product_facts, selling_points, keyword_analysis, positioning, "
                    "content_patterns, risk_notes, and evidence."
                ),
            )
            response = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=(
                                "Create the final single-competitor analysis JSON. "
                                "The heuristic_seed is only a starting point; improve it "
                                "using the listing extraction while preserving traceability.\n"
                                f"{json.dumps(context, ensure_ascii=False)}"
                            )
                        )
                    ]
                }
            )
            await record_model_invocation(
                session,
                model_config_id=model_config.id,
                feature_name="竞品单条分析",
                api_endpoint="POST /api/v1/competitors/{competitor_input_id}/analyze",
                response=response,
            )
        except Exception as exc:
            try:
                return normalize_single_competitor_analysis_result(
                    heuristic_seed,
                    heuristic_seed,
                )
            except Exception as fallback_exc:
                raise CompetitorAnalysisLLMError(
                    f"single competitor LLM analysis failed: {exc}"
                ) from fallback_exc

        structured_response = response.get("structured_response")
        try:
            if isinstance(structured_response, SingleCompetitorAnalysisOutput):
                return normalize_single_competitor_analysis_result(
                    structured_response.model_dump(),
                    heuristic_seed,
                )
            if isinstance(structured_response, dict):
                parsed = SingleCompetitorAnalysisOutput.model_validate(
                    structured_response
                ).model_dump()
                return normalize_single_competitor_analysis_result(parsed, heuristic_seed)
        except Exception as exc:
            try:
                return normalize_single_competitor_analysis_result(
                    heuristic_seed,
                    heuristic_seed,
                )
            except Exception as fallback_exc:
                raise CompetitorAnalysisLLMError(
                    f"single competitor LLM analysis returned invalid structure: {exc}"
                ) from fallback_exc
        return normalize_single_competitor_analysis_result(heuristic_seed, heuristic_seed)

    async def aggregate_competitor_analysis(
        self,
        session: AsyncSession,
        brief_id: str,
    ) -> CompetitorAnalysis | None:
        """Generate the final aggregated competitor analysis report with the LLM."""
        brief_result = await session.execute(select(ProductBrief).where(ProductBrief.id == brief_id))
        brief = brief_result.scalar_one_or_none()
        if brief is None:
            raise CompetitorAggregationError("brief not found")

        summary_result = await session.execute(
            select(CompetitorSummary)
            .where(CompetitorSummary.brief_id == brief_id)
            .order_by(CompetitorSummary.created_at.desc())
        )
        summaries = [
            summary
            for summary in summary_result.scalars().all()
            if isinstance(summary.analysis_result, dict)
        ]
        if not summaries:
            raise CompetitorAggregationError("no completed competitor analyses found")

        input_result = await session.execute(
            select(CompetitorInput).where(
                CompetitorInput.brief_id == brief_id,
                CompetitorInput.status.in_(["pending", "imported", "queued", "running"]),
            )
        )
        if input_result.scalars().first() is not None:
            raise CompetitorAggregationError(
                "competitor analyses are still running; aggregate after all inputs finish"
            )

        if len(summaries) == 1:
            report = build_single_competitor_final_report(brief, summaries[0])
            package = build_competitor_analysis_package_from_report(report)
            validate_competitor_analysis_package(package)
            analysis = await self._upsert_aggregated_analysis(
                session,
                brief=brief,
                competitor_count=1,
                report=package["report"],
                action_brief=package["action_brief"],
                constraints=package["constraints"],
                status_value="completed",
                error_message=None,
                model_name="single-competitor-direct",
            )
            await session.commit()
            await session.refresh(analysis)
            return analysis

        try:
            package = await self._generate_aggregated_competitor_package(session, brief, summaries)
        except Exception as exc:
            report = build_aggregated_competitor_report(brief, summaries)
            package = build_competitor_analysis_package_from_report(report)
            validate_competitor_analysis_package(package)
            analysis = await self._upsert_aggregated_analysis(
                session,
                brief=brief,
                competitor_count=len(summaries),
                report=package["report"],
                action_brief=package["action_brief"],
                constraints=package["constraints"],
                status_value="completed",
                error_message=(
                    "LLM aggregation failed; deterministic fallback used: "
                    f"{exc}"
                ),
                model_name="deterministic-fallback",
            )
            await session.commit()
            await session.refresh(analysis)
            return analysis

        analysis = await self._upsert_aggregated_analysis(
            session,
            brief=brief,
            competitor_count=len(summaries),
            report=package["report"],
            action_brief=package["action_brief"],
            constraints=package["constraints"],
            status_value="completed",
            error_message=None,
            model_name="llm",
        )
        await session.commit()
        await session.refresh(analysis)
        return analysis

    async def _generate_aggregated_competitor_package(
        self,
        session: AsyncSession,
        brief: ProductBrief,
        summaries: list[CompetitorSummary],
    ) -> dict[str, Any]:
        """Use the configured LLM to generate the final aggregate analysis package."""
        context = build_aggregation_llm_context(brief, summaries)
        model, model_config = await get_chat_model_with_config(session)
        structured_model = model.with_structured_output(
            CompetitorAnalysisPackageOutput,
            include_raw=True,
        )
        response = await structured_model.ainvoke(
            [
                SystemMessage(content=build_aggregation_system_prompt()),
                HumanMessage(
                    content=(
                        "Generate the final competitor analysis package from "
                        "this compact context:\n"
                        f"{json.dumps(context, ensure_ascii=False)}"
                    )
                ),
            ]
        )
        await record_model_invocation(
            session,
            model_config_id=model_config.id,
            feature_name="竞品聚合分析",
            api_endpoint="POST /api/v1/competitors/by-brief/{brief_id}/aggregate-analysis",
            response=response,
        )
        structured_response = (
            response.get("parsed") if isinstance(response, dict) else response
        )
        try:
            if isinstance(structured_response, CompetitorAnalysisPackageOutput):
                package = normalize_aggregated_competitor_package(
                    structured_response.model_dump(),
                    brief,
                    summaries,
                )
                validate_competitor_analysis_package(package)
                return package
            if isinstance(structured_response, dict):
                parsed = CompetitorAnalysisPackageOutput.model_validate(
                    structured_response
                ).model_dump()
                parsed = normalize_aggregated_competitor_package(parsed, brief, summaries)
                validate_competitor_analysis_package(parsed)
                return parsed
        except Exception as exc:
            raise CompetitorAggregationError(
                f"aggregated competitor LLM analysis returned invalid structure: {exc}"
            ) from exc
        parsing_error = response.get("parsing_error") if isinstance(response, dict) else None
        if parsing_error:
            raise CompetitorAggregationError(
                "aggregated competitor LLM analysis returned invalid structure: "
                f"{parsing_error}"
            )
        raise CompetitorAggregationError(
            "aggregated competitor LLM analysis returned no structured output"
        )

    async def _upsert_aggregated_analysis(
        self,
        session: AsyncSession,
        *,
        brief: ProductBrief,
        competitor_count: int,
        report: dict[str, Any] | None,
        action_brief: dict[str, Any] | None,
        constraints: dict[str, Any] | None,
        status_value: str,
        error_message: str | None,
        model_name: str,
    ) -> CompetitorAnalysis:
        """Persist the current final aggregate analysis state."""
        analysis_result = await session.execute(
            select(CompetitorAnalysis).where(CompetitorAnalysis.brief_id == brief.id)
        )
        analysis = analysis_result.scalar_one_or_none()
        values = {
            "conversation_id": brief.conversation_id,
            "status": status_value,
            "competitor_count": competitor_count,
            "report": report,
            "action_brief": action_brief,
            "constraints": constraints,
            "error_message": error_message,
            "model_name": model_name,
        }
        if analysis is None:
            analysis = CompetitorAnalysis(brief_id=brief.id, **values)
            session.add(analysis)
        else:
            for key, value in values.items():
                setattr(analysis, key, value)
        await session.flush()
        return analysis

    async def _mark_failed(
        self,
        session: AsyncSession,
        job: Job,
        competitor_input: CompetitorInput,
        error_message: str,
    ) -> tuple[Job, None]:
        """Record failed analysis without raising a 500 response."""
        competitor_input.status = "failed"
        job.status = "failed"
        job.finished_at = now_app_timezone()
        job.error_message = error_message
        await session.commit()
        await session.refresh(job)
        return job, None

    async def _advance_conversation(self, session: AsyncSession, conversation_id: str) -> None:
        """Move the conversation to the draft generation step after a summary exists."""
        result = await session.execute(select(Conversation).where(Conversation.id == conversation_id))
        conversation = result.scalar_one_or_none()
        if conversation is not None:
            conversation.current_step = "generate_draft"


def extract_competitor_content(html: str) -> ExtractedCompetitorContent:
    """Extract title, bullets, and description from common Amazon listing markup."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = first_text(
        soup,
        [
            "#productTitle",
            "span#productTitle",
            "#pqv-title",
            "meta[property='og:title']",
            "meta[name='title']",
            "title",
        ],
    )
    bullets = extract_bullets(soup)
    description_text = first_text(
        soup,
        [
            "#productDescription",
            "#pqv-description",
            "#aplus_feature_div",
            "#feature-bullets",
            "#pqv-feature-bullets",
        ],
    )
    raw_text = clean_text(soup.get_text("\n"))
    return ExtractedCompetitorContent(
        title=normalize_extracted_title(title),
        bullets=bullets,
        description_text=description_text,
        raw_text=raw_text[:20000],
    )


def has_extractable_competitor_content(content: ExtractedCompetitorContent) -> bool:
    """Return whether a page contains usable listing content."""
    return bool(content.title or content.bullets or content.description_text)


def build_fetch_urls(url: str, asin: str | None) -> list[str]:
    """Build URL variants that Amazon commonly serves with different markup."""
    urls = [url]
    effective_asin = asin or extract_asin_from_url(url)
    if effective_asin:
        urls.extend(
            [
                f"https://www.amazon.com/dp/{effective_asin}?th=1&psc=1&language=en_US",
                f"https://www.amazon.com/gp/product/{effective_asin}?th=1&psc=1&language=en_US",
                f"https://www.amazon.com/gp/aw/d/{effective_asin}?th=1&psc=1&language=en_US",
            ]
        )
    return dedupe_preserve_order(urls)


def extract_asin_from_url(url: str) -> str | None:
    """Extract an ASIN from common Amazon detail URLs."""
    parsed = urlparse(url)
    match = re.search(r"/(?:dp|gp/product|product|gp/aw/d)/([A-Z0-9]{10})(?:[/?#]|$)", parsed.path, re.I)
    return match.group(1).upper() if match else None


def dedupe_preserve_order(values: list[str]) -> list[str]:
    """Remove duplicate URL candidates while keeping their order."""
    seen = set()
    deduped = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def is_amazon_continue_page(html: str) -> bool:
    """Detect Amazon's lightweight continue-shopping interstitial."""
    lowered = html.lower()
    return (
        "opfcaptcha.amazon.com" in lowered
        or "/errors/validatecaptcha" in lowered
        or "click the button below to continue shopping" in lowered
    )


async def submit_amazon_continue_form(
    client: httpx.AsyncClient,
    response: httpx.Response,
) -> httpx.Response:
    """Submit Amazon's continue-shopping form with the same cookie jar."""
    soup = BeautifulSoup(response.text, "html.parser")
    form = soup.select_one("form[action*='validateCaptcha']")
    if form is None:
        return response

    action = form.get("action") or "/errors/validateCaptcha"
    target_url = urljoin(str(response.url), action)
    params = {
        input_tag.get("name"): input_tag.get("value", "")
        for input_tag in form.select("input[name]")
        if input_tag.get("name")
    }
    continued = await client.get(target_url, params=params, headers=REQUEST_HEADERS)
    if continued.is_redirect:
        location = continued.headers.get("location")
        if location:
            continued = await client.get(urljoin(str(continued.url), location), headers=REQUEST_HEADERS)
    return continued


def first_text(soup: BeautifulSoup, selectors: list[str]) -> str | None:
    """Return the first non-empty text or meta content for a list of selectors."""
    for selector in selectors:
        element = soup.select_one(selector)
        if element is None:
            continue
        value = element.get("content") if element.name == "meta" else element.get_text(" ")
        cleaned = clean_text(value or "")
        if cleaned and is_valid_product_text(cleaned):
            return cleaned
    return None


def extract_bullets(soup: BeautifulSoup) -> list[str]:
    """Extract bullet point text from common Amazon feature bullet containers."""
    candidates = soup.select(
        "#feature-bullets li span.a-list-item, "
        "#feature-bullets li, "
        "#featurebullets_feature_div li span.a-list-item, "
        "#featurebullets_feature_div li, "
        "#pqv-feature-bullets li span.a-list-item, "
        "#pqv-feature-bullets li"
    )
    bullets = []
    seen = set()
    for candidate in candidates:
        text = clean_text(candidate.get_text(" "))
        if not text or text in seen or not is_valid_bullet_text(text):
            continue
        seen.add(text)
        bullets.append(text)
    return bullets[:8]


def is_valid_product_text(value: str) -> bool:
    """Filter generic Amazon page chrome text."""
    normalized = value.strip().lower()
    return normalized not in {
        "amazon.com",
        "amazon.com: online shopping for electronics, apparel, computers, books, dvds & more",
        "click the button below to continue shopping",
    }


def normalize_extracted_title(value: str | None) -> str | None:
    """Clean Amazon wrapper text from extracted product titles."""
    if not value:
        return None
    title = re.sub(r"^product summary:\s*", "", value.strip(), flags=re.I)
    title = re.sub(r"\s*:\s*amazon\.com\s*:.*$", "", title, flags=re.I)
    title = re.sub(r"\s*-\s*amazon\.com\s*$", "", title, flags=re.I)
    cleaned = clean_text(title)
    return cleaned if cleaned and is_valid_product_text(cleaned) else None


def is_valid_bullet_text(value: str) -> bool:
    """Filter non-content bullets from Amazon layout chrome."""
    normalized = value.strip().lower()
    if not is_valid_product_text(value):
        return False
    ignored_prefixes = (
        "make sure this fits",
        "to see our price",
        "customer reviews",
        "other sellers",
        "available at a lower price",
    )
    return not any(normalized.startswith(prefix) for prefix in ignored_prefixes)


def clean_text(value: str) -> str:
    """Collapse whitespace for extracted listing text."""
    return " ".join(value.split())


def build_feature_summary(content: ExtractedCompetitorContent) -> list[str]:
    """Use bullets as a simple V1 feature summary."""
    if content.bullets:
        return content.bullets[:5]
    if content.description_text:
        return [content.description_text[:300]]
    return []


def build_extraction_result(
    content: ExtractedCompetitorContent,
    keywords: list[str],
    snapshot_path: str,
) -> dict[str, Any]:
    """Build the traceable raw listing extraction payload."""
    return {
        "listing_content": {
            "title": content.title,
            "bullets": content.bullets,
            "description": content.description_text,
            "search_terms": keywords[:12],
            "raw_text_excerpt": content.raw_text[:2000],
        },
        "snapshot_path": snapshot_path,
    }


def build_single_competitor_analysis(
    competitor_input: CompetitorInput,
    content: ExtractedCompetitorContent,
    keywords: list[str],
    snapshot_path: str,
) -> dict[str, Any]:
    """Build a complete rule-based analysis for one competitor."""
    features = build_feature_summary(content)
    risks = build_risk_summary(content)
    scenarios = pick_terms_by_markers(content, ["for", "with", "outdoor", "home", "office", "travel"])
    audiences = pick_terms_by_markers(content, ["kids", "men", "women", "baby", "pet", "professional"])
    return {
        "source": {
            "competitor_input_id": competitor_input.id,
            "url": competitor_input.normalized_url,
            "asin": competitor_input.asin,
            "snapshot_path": snapshot_path,
            "confidence": estimate_extraction_confidence(content),
        },
        "product_facts": {
            "title": content.title,
            "visible_specifications": infer_visible_specifications(content),
            "brand": "unknown",
            "price": "unknown",
            "rating": "unknown",
            "review_count": "unknown",
            "category": "unknown",
            "variants": [],
        },
        "selling_points": features,
        "keyword_analysis": {
            "primary": keywords[:5],
            "long_tail": build_long_tail_keywords(content),
            "attributes": infer_attribute_terms(content),
            "scenarios": scenarios,
            "audiences": audiences,
            "risk_terms": risks,
        },
        "positioning": {
            "target_audience": audiences,
            "use_scenarios": scenarios,
            "pain_points": infer_pain_points(content),
            "benefits": features,
            "tone": infer_tone(content),
        },
        "content_patterns": {
            "title_pattern": infer_title_pattern(content.title),
            "bullet_pattern": infer_bullet_pattern(content.bullets),
            "information_density": infer_information_density(content),
        },
        "risk_notes": risks,
        "evidence": build_evidence(content),
    }


def normalize_single_competitor_analysis_result(
    result: dict[str, Any],
    heuristic_seed: dict[str, Any],
) -> dict[str, Any]:
    """Normalize one competitor analysis to the single required stored shape."""
    seed_keywords = heuristic_seed.get("keyword_analysis", {})
    source = result.get("source") if isinstance(result.get("source"), dict) else {}
    product_facts = (
        result.get("product_facts") if isinstance(result.get("product_facts"), dict) else {}
    )
    keyword_analysis = (
        result.get("keyword_analysis") if isinstance(result.get("keyword_analysis"), dict) else {}
    )
    positioning = result.get("positioning") if isinstance(result.get("positioning"), dict) else {}
    content_patterns = (
        result.get("content_patterns") if isinstance(result.get("content_patterns"), dict) else {}
    )
    normalized = {
        "source": {
            **dict(heuristic_seed.get("source") or {}),
            **source,
        },
        "product_facts": {
            **dict(heuristic_seed.get("product_facts") or {}),
            **product_facts,
        },
        "selling_points": first_non_empty_text_list(
            result.get("selling_points"),
            heuristic_seed.get("selling_points"),
        ),
        "keyword_analysis": {
            "primary": first_non_empty_text_list(
                keyword_analysis.get("primary"),
                seed_keywords.get("primary") if isinstance(seed_keywords, dict) else [],
            ),
            "long_tail": first_non_empty_text_list(
                keyword_analysis.get("long_tail"),
                seed_keywords.get("long_tail") if isinstance(seed_keywords, dict) else [],
            ),
            "attributes": first_non_empty_text_list(
                keyword_analysis.get("attributes"),
                seed_keywords.get("attributes") if isinstance(seed_keywords, dict) else [],
            ),
            "scenarios": first_non_empty_text_list(
                keyword_analysis.get("scenarios"),
                seed_keywords.get("scenarios") if isinstance(seed_keywords, dict) else [],
            ),
            "audiences": first_non_empty_text_list(
                keyword_analysis.get("audiences"),
                seed_keywords.get("audiences") if isinstance(seed_keywords, dict) else [],
            ),
            "risk_terms": first_non_empty_text_list(
                keyword_analysis.get("risk_terms"),
                seed_keywords.get("risk_terms") if isinstance(seed_keywords, dict) else [],
            ),
        },
        "positioning": {
            "target_audience": first_non_empty_text_list(
                positioning.get("target_audience"),
                (heuristic_seed.get("positioning") or {}).get("target_audience"),
            ),
            "use_scenarios": first_non_empty_text_list(
                positioning.get("use_scenarios"),
                (heuristic_seed.get("positioning") or {}).get("use_scenarios"),
            ),
            "pain_points": first_non_empty_text_list(
                positioning.get("pain_points"),
                (heuristic_seed.get("positioning") or {}).get("pain_points"),
            ),
            "benefits": first_non_empty_text_list(
                positioning.get("benefits"),
                (heuristic_seed.get("positioning") or {}).get("benefits"),
            ),
            "tone": clean_optional_text(
                positioning.get("tone") or (heuristic_seed.get("positioning") or {}).get("tone")
            ),
        },
        "content_patterns": {
            "title_pattern": clean_optional_text(
                content_patterns.get("title_pattern")
                or (heuristic_seed.get("content_patterns") or {}).get("title_pattern")
            ),
            "bullet_pattern": clean_optional_text(
                content_patterns.get("bullet_pattern")
                or (heuristic_seed.get("content_patterns") or {}).get("bullet_pattern")
            ),
            "information_density": clean_optional_text(
                content_patterns.get("information_density")
                or (heuristic_seed.get("content_patterns") or {}).get("information_density")
            ),
        },
        "risk_notes": first_non_empty_text_list(
            result.get("risk_notes"),
            heuristic_seed.get("risk_notes"),
        ),
        "evidence": result.get("evidence")
        if isinstance(result.get("evidence"), list)
        else heuristic_seed.get("evidence", []),
    }
    validate_single_competitor_analysis_result(normalized)
    return normalized


def validate_single_competitor_analysis_result(result: dict[str, Any]) -> None:
    """Reject inconsistent single-competitor analysis before persistence."""
    keyword_analysis = result.get("keyword_analysis") or {}
    positioning = result.get("positioning") or {}
    content_patterns = result.get("content_patterns") or {}
    missing = [
        field
        for field, value in {
            "source.competitor_input_id": (result.get("source") or {}).get("competitor_input_id"),
            "keyword_analysis.primary": keyword_analysis.get("primary"),
        }.items()
        if value in (None, "", [], {})
    ]
    invalid_lists = [
        field
        for field, value in {
            "selling_points": result.get("selling_points"),
            "keyword_analysis.primary": keyword_analysis.get("primary"),
            "keyword_analysis.long_tail": keyword_analysis.get("long_tail"),
            "keyword_analysis.attributes": keyword_analysis.get("attributes"),
            "keyword_analysis.scenarios": keyword_analysis.get("scenarios"),
            "keyword_analysis.audiences": keyword_analysis.get("audiences"),
            "keyword_analysis.risk_terms": keyword_analysis.get("risk_terms"),
            "positioning.target_audience": positioning.get("target_audience"),
            "positioning.use_scenarios": positioning.get("use_scenarios"),
            "positioning.pain_points": positioning.get("pain_points"),
            "positioning.benefits": positioning.get("benefits"),
            "risk_notes": result.get("risk_notes"),
            "evidence": result.get("evidence"),
        }.items()
        if not isinstance(value, list)
    ]
    invalid_text = [
        field
        for field, value in {
            "content_patterns.title_pattern": content_patterns.get("title_pattern"),
            "content_patterns.bullet_pattern": content_patterns.get("bullet_pattern"),
            "content_patterns.information_density": content_patterns.get("information_density"),
        }.items()
        if value is not None and not isinstance(value, str)
    ]
    errors = missing + invalid_lists + invalid_text
    if errors:
        raise CompetitorAnalysisLLMError(
            "single competitor analysis has invalid required structure: " + ", ".join(errors)
        )


def first_non_empty_text_list(*values: Any) -> list[str]:
    """Return the first non-empty flattened text list."""
    for value in values:
        flattened = dedupe_text(flatten_text_values(value))
        if flattened:
            return flattened
    return []


def clean_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    cleaned = clean_text(str(value))
    return cleaned or None


def build_aggregated_competitor_report(
    brief: ProductBrief,
    summaries: list[CompetitorSummary],
) -> dict[str, Any]:
    """Build the read-only aggregated competitor analysis report."""
    analyses = [
        summary.analysis_result
        for summary in summaries
        if isinstance(summary.analysis_result, dict)
    ]
    all_features = flatten_text_values(
        [analysis.get("selling_points", []) for analysis in analyses]
        + [summary.feature_summary for summary in summaries]
    )
    all_keywords = flatten_text_values(
        [
            analysis.get("keyword_analysis", {}).get("primary", [])
            for analysis in analyses
            if isinstance(analysis.get("keyword_analysis"), dict)
        ]
        + [summary.keyword_summary for summary in summaries]
    )
    all_risks = flatten_text_values(
        [analysis.get("risk_notes", []) for analysis in analyses] + [summary.risk_summary for summary in summaries]
    )
    all_scenarios = flatten_text_values(
        [
            analysis.get("positioning", {}).get("use_scenarios", [])
            for analysis in analyses
            if isinstance(analysis.get("positioning"), dict)
        ]
    )
    all_audiences = flatten_text_values(
        [
            analysis.get("positioning", {}).get("target_audience", [])
            for analysis in analyses
            if isinstance(analysis.get("positioning"), dict)
        ]
    )
    common_features = most_common_values(all_features, limit=10)
    common_keywords = most_common_values(all_keywords, limit=20)
    common_risks = most_common_values(all_risks, limit=20)
    comparison_matrix = build_comparison_matrix(summaries)
    opportunities = build_aggregate_differentiation_opportunities(
        brief,
        common_features,
        common_keywords,
        common_risks,
    )
    return {
        "brief": {
            "id": brief.id,
            "product_name": brief.product_name,
            "brand": brief.brand,
            "category": brief.category,
            "marketplace": brief.marketplace,
            "language": brief.language,
            "color": brief.color,
            "quantity": brief.quantity,
        },
        "competitor_count": len(summaries),
        "market_patterns": {
            "common_features": common_features,
            "common_benefits": common_features[:5],
            "common_scenarios": most_common_values(all_scenarios, limit=10),
            "common_audiences": most_common_values(all_audiences, limit=10),
            "common_keywords": common_keywords,
            "common_title_patterns": most_common_values(
                [
                    str(analysis.get("content_patterns", {}).get("title_pattern", ""))
                    for analysis in analyses
                    if isinstance(analysis.get("content_patterns"), dict)
                ],
                limit=5,
            ),
            "common_bullet_patterns": most_common_values(
                [
                    str(analysis.get("content_patterns", {}).get("bullet_pattern", ""))
                    for analysis in analyses
                    if isinstance(analysis.get("content_patterns"), dict)
                ],
                limit=5,
            ),
        },
        "comparison_matrix": comparison_matrix,
        "keyword_insights": {
            "primary": common_keywords[:8],
            "long_tail": most_common_values(
                flatten_text_values(
                    [
                        analysis.get("keyword_analysis", {}).get("long_tail", [])
                        for analysis in analyses
                        if isinstance(analysis.get("keyword_analysis"), dict)
                    ]
                ),
                limit=12,
            ),
            "attributes": most_common_values(
                flatten_text_values(
                    [
                        analysis.get("keyword_analysis", {}).get("attributes", [])
                        for analysis in analyses
                        if isinstance(analysis.get("keyword_analysis"), dict)
                    ]
                ),
                limit=12,
            ),
            "risk_terms": common_risks,
        },
        "differentiation_opportunities": opportunities,
        "risk_summary": common_risks,
        "recommended_listing_strategy": {
            "positioning": build_positioning_strategy(brief, common_features),
            "title_strategy": [
                "Lead with verified brand, primary keyword, and strongest supported differentiator.",
                "Use competitor keyword patterns as category signals without copying titles.",
            ],
            "bullet_strategy": [
                "Cover common market expectations first, then reserve bullets for verified differentiation.",
                "Translate features into shopper benefits only when supported by the Brief.",
            ],
            "description_strategy": [
                "Use the description to connect use scenarios, audience fit, and verified product facts.",
            ],
            "keyword_strategy": common_keywords[:20],
            "avoid_strategy": [
                f"Avoid competitor risk term: {term}" for term in common_risks[:10]
            ],
        },
        "missing_user_facts": infer_missing_user_facts(brief),
    }


def build_single_competitor_final_report(
    brief: ProductBrief,
    summary: CompetitorSummary,
) -> dict[str, Any]:
    """Use one completed competitor analysis directly as the final report."""
    analysis = summary.analysis_result if isinstance(summary.analysis_result, dict) else {}
    keyword_analysis = analysis.get("keyword_analysis", {})
    positioning = analysis.get("positioning", {})
    content_patterns = analysis.get("content_patterns", {})
    selling_points = flatten_text_values(analysis.get("selling_points", []))
    primary_keywords = flatten_text_values(
        keyword_analysis.get("primary", []) if isinstance(keyword_analysis, dict) else []
    )
    long_tail = flatten_text_values(
        keyword_analysis.get("long_tail", []) if isinstance(keyword_analysis, dict) else []
    )
    attributes = flatten_text_values(
        keyword_analysis.get("attributes", []) if isinstance(keyword_analysis, dict) else []
    )
    risk_terms = flatten_text_values(analysis.get("risk_notes", summary.risk_summary or []))
    scenarios = flatten_text_values(
        positioning.get("use_scenarios", []) if isinstance(positioning, dict) else []
    )
    audiences = flatten_text_values(
        positioning.get("target_audience", []) if isinstance(positioning, dict) else []
    )
    return {
        "brief": {
            "id": brief.id,
            "product_name": brief.product_name,
            "brand": brief.brand,
            "category": brief.category,
            "marketplace": brief.marketplace,
            "language": brief.language,
            "color": brief.color,
            "quantity": brief.quantity,
        },
        "competitor_count": 1,
        "market_patterns": {
            "common_features": selling_points,
            "common_benefits": flatten_text_values(
                positioning.get("benefits", []) if isinstance(positioning, dict) else []
            )
            or selling_points,
            "common_scenarios": scenarios,
            "common_audiences": audiences,
            "common_keywords": primary_keywords,
            "common_title_patterns": [
                str(content_patterns.get("title_pattern"))
            ]
            if isinstance(content_patterns, dict) and content_patterns.get("title_pattern")
            else [],
            "common_bullet_patterns": [
                str(content_patterns.get("bullet_pattern"))
            ]
            if isinstance(content_patterns, dict) and content_patterns.get("bullet_pattern")
            else [],
        },
        "comparison_matrix": build_comparison_matrix([summary]),
        "keyword_insights": {
            "primary": primary_keywords,
            "long_tail": long_tail,
            "attributes": attributes,
            "risk_terms": risk_terms,
        },
        "differentiation_opportunities": [
            "Only one completed competitor is available; use this competitor as a reference sample, not as a market-wide pattern.",
            "Add more completed competitor analyses before making category-level conclusions.",
        ],
        "risk_summary": risk_terms,
        "recommended_listing_strategy": {
            "positioning": build_positioning_strategy(brief, selling_points),
            "title_strategy": [
                "Use verified Brief facts first; use the single competitor only for category language reference.",
            ],
            "bullet_strategy": [
                "Cover supported product benefits without copying the competitor's claims or wording.",
            ],
            "description_strategy": [
                "Connect verified product facts with relevant scenarios from the single competitor analysis.",
            ],
            "keyword_strategy": primary_keywords + long_tail,
            "avoid_strategy": [f"Avoid competitor risk term: {term}" for term in risk_terms],
        },
        "missing_user_facts": infer_missing_user_facts(brief),
        "aggregation_note": (
            "Only one completed competitor analysis was available, so no LLM aggregation was run."
        ),
    }


def validate_aggregated_competitor_report(report: dict[str, Any]) -> None:
    """Ensure the final LLM report contains every UI-required section."""
    market_patterns = report.get("market_patterns") or {}
    keyword_insights = report.get("keyword_insights") or {}
    strategy = report.get("recommended_listing_strategy") or {}
    required_checks = {
        "market_patterns.common_features": market_patterns.get("common_features"),
        "market_patterns.common_keywords": market_patterns.get("common_keywords"),
        "keyword_insights.primary": keyword_insights.get("primary"),
        "comparison_matrix": report.get("comparison_matrix"),
        "differentiation_opportunities": report.get("differentiation_opportunities"),
        "recommended_listing_strategy.positioning": strategy.get("positioning"),
        "recommended_listing_strategy.title_strategy": strategy.get("title_strategy"),
        "recommended_listing_strategy.bullet_strategy": strategy.get("bullet_strategy"),
        "recommended_listing_strategy.keyword_strategy": strategy.get("keyword_strategy"),
    }
    missing = [
        field
        for field, value in required_checks.items()
        if value in (None, "", [], {})
    ]
    if missing:
        raise CompetitorAggregationError(
            "aggregated competitor LLM analysis missing required fields: "
            + ", ".join(missing)
        )
    required_list_fields = {
        "risk_summary": report.get("risk_summary"),
        "missing_user_facts": report.get("missing_user_facts"),
        "keyword_insights.risk_terms": keyword_insights.get("risk_terms"),
        "recommended_listing_strategy.avoid_strategy": strategy.get("avoid_strategy"),
    }
    invalid_lists = [
        field
        for field, value in required_list_fields.items()
        if not isinstance(value, list)
    ]
    if invalid_lists:
        raise CompetitorAggregationError(
            "aggregated competitor LLM analysis has invalid list fields: "
            + ", ".join(invalid_lists)
        )


def build_aggregation_system_prompt() -> str:
    """Return the one-shot aggregate analysis prompt."""
    return (
        "Create an aggregated Amazon competitor analysis for listing generation. "
        "Synthesize the completed competitor analyses into market patterns, keyword "
        "insights, differentiation opportunities, risks, and a practical listing "
        "strategy. Prefer shared signals and meaningful contrasts over repeating each "
        "competitor one by one. Use only the provided data: do not invent product "
        "facts, do not copy competitor wording, and do not treat competitor claims as "
        "facts about the user's product. Mark missing user facts that require "
        "confirmation. Return the required structured package with three sections: "
        "report for human review, action_brief for the generation agent, and "
        "constraints for hard safety limits."
    )


def normalize_aggregated_competitor_package(
    package: dict[str, Any],
    brief: ProductBrief,
    summaries: list[CompetitorSummary],
) -> dict[str, Any]:
    """Fill empty required aggregate fields from deterministic competitor signals."""
    fallback_report = build_aggregated_competitor_report(brief, summaries)
    report = package.get("report") if isinstance(package.get("report"), dict) else {}
    normalized_report = fill_empty_values(report, fallback_report)
    fallback_package = build_competitor_analysis_package_from_report(normalized_report)
    action_brief = package.get("action_brief")
    constraints = package.get("constraints")
    return {
        "report": normalized_report,
        "action_brief": fill_empty_values(
            action_brief if isinstance(action_brief, dict) else {},
            fallback_package["action_brief"],
        ),
        "constraints": fill_empty_values(
            constraints if isinstance(constraints, dict) else {},
            fallback_package["constraints"],
        ),
    }


def fill_empty_values(value: Any, fallback: Any) -> Any:
    """Recursively prefer value, using fallback only when value is empty."""
    if isinstance(value, dict) and isinstance(fallback, dict):
        merged = dict(value)
        for key, fallback_value in fallback.items():
            merged[key] = fill_empty_values(merged.get(key), fallback_value)
        return merged
    if value in (None, "", [], {}):
        return fallback
    return value


def build_competitor_analysis_package_from_report(report: dict[str, Any]) -> dict[str, Any]:
    """Build action_brief and constraints from a valid aggregate report."""
    market_patterns = report.get("market_patterns") or {}
    keyword_insights = report.get("keyword_insights") or {}
    strategy = report.get("recommended_listing_strategy") or {}
    risk_summary = flatten_text_values(report.get("risk_summary") or [])
    risk_terms = flatten_text_values(keyword_insights.get("risk_terms") or [])
    missing_user_facts = flatten_text_values(report.get("missing_user_facts") or [])
    return {
        "report": report,
        "action_brief": {
            "positioning": strategy.get("positioning"),
            "title_plan": strategy.get("title_strategy") or [],
            "bullet_plan": strategy.get("bullet_strategy") or [],
            "description_plan": strategy.get("description_strategy") or [],
            "keywords_to_use": flatten_text_values(keyword_insights.get("primary") or [])
            + flatten_text_values(keyword_insights.get("long_tail") or []),
            "search_terms": strategy.get("keyword_strategy") or [],
            "differentiators": report.get("differentiation_opportunities") or [],
            "must_cover": flatten_text_values(market_patterns.get("common_features") or [])
            + flatten_text_values(market_patterns.get("common_benefits") or []),
        },
        "constraints": {
            "avoid_terms": dedupe_text(risk_summary + risk_terms),
            "avoid_claim_types": strategy.get("avoid_strategy") or [],
            "do_not_infer": missing_user_facts,
            "requires_user_evidence": missing_user_facts,
            "competitor_copy_policy": "do_not_copy",
        },
    }


def validate_competitor_analysis_package(package: dict[str, Any]) -> None:
    """Ensure stored aggregate package has report, action_brief, and constraints."""
    report = package.get("report")
    action_brief = package.get("action_brief") or {}
    constraints = package.get("constraints") or {}
    if not isinstance(report, dict):
        raise CompetitorAggregationError("competitor analysis package missing report")
    validate_aggregated_competitor_report(report)
    required_action_fields = {
        "action_brief.positioning": action_brief.get("positioning"),
        "action_brief.title_plan": action_brief.get("title_plan"),
        "action_brief.bullet_plan": action_brief.get("bullet_plan"),
        "action_brief.description_plan": action_brief.get("description_plan"),
        "action_brief.keywords_to_use": action_brief.get("keywords_to_use"),
        "action_brief.differentiators": action_brief.get("differentiators"),
        "action_brief.must_cover": action_brief.get("must_cover"),
    }
    required_constraints = {
        "constraints.competitor_copy_policy": constraints.get("competitor_copy_policy"),
    }
    missing = [
        field
        for field, value in {**required_action_fields, **required_constraints}.items()
        if value in (None, "", [], {})
    ]
    if missing:
        raise CompetitorAggregationError(
            "competitor analysis package missing required fields: " + ", ".join(missing)
        )
    required_list_fields = {
        "constraints.avoid_terms": constraints.get("avoid_terms"),
        "constraints.avoid_claim_types": constraints.get("avoid_claim_types"),
        "constraints.do_not_infer": constraints.get("do_not_infer"),
        "constraints.requires_user_evidence": constraints.get("requires_user_evidence"),
    }
    invalid_lists = [
        field
        for field, value in required_list_fields.items()
        if not isinstance(value, list)
    ]
    if invalid_lists:
        raise CompetitorAggregationError(
            "competitor analysis package has invalid list fields: "
            + ", ".join(invalid_lists)
        )


def build_aggregation_llm_context(
    brief: ProductBrief,
    summaries: list[CompetitorSummary],
) -> dict[str, Any]:
    """Build a compact LLM input for final aggregate analysis."""
    compact_competitors = []
    for summary in summaries:
        analysis = summary.analysis_result if isinstance(summary.analysis_result, dict) else {}
        extraction = summary.extraction_result if isinstance(summary.extraction_result, dict) else {}
        compact_competitors.append(
            {
                "competitor_input_id": summary.competitor_input_id,
                "title": summary.title,
                "listing_content": {
                    "bullets": (summary.bullets or [])[:5],
                    "description_excerpt": (summary.description_text or "")[:700],
                    "search_terms": summary.search_terms or [],
                },
                "single_competitor_analysis": {
                    "product_facts": analysis.get("product_facts", {}),
                    "selling_points": analysis.get("selling_points", []),
                    "keyword_analysis": analysis.get("keyword_analysis", {}),
                    "positioning": analysis.get("positioning", {}),
                    "content_patterns": analysis.get("content_patterns", {}),
                    "risk_notes": analysis.get("risk_notes", []),
                    "evidence": (analysis.get("evidence", []) or [])[:6]
                    if isinstance(analysis.get("evidence", []), list)
                    else [],
                },
                "source": {
                    "snapshot_path": summary.raw_content_snapshot,
                    "extraction_snapshot_path": extraction.get("snapshot_path"),
                },
            }
        )
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
        "competitor_count": len(compact_competitors),
        "competitors": compact_competitors,
        "output_requirements": {
            "synthesize": "Do not concatenate all competitor details; produce a concise final report.",
            "copy_safety": "Do not copy competitor text into recommendations.",
            "fact_safety": "Do not convert competitor facts into product facts for the user's product.",
        },
    }


def build_keyword_summary(content: ExtractedCompetitorContent, limit: int = 20) -> list[str]:
    """Extract frequent meaningful words from title, bullets, and description."""
    text = " ".join(
        item
        for item in [content.title, *content.bullets, content.description_text]
        if item
    ).lower()
    counts: dict[str, int] = {}
    for word in re_words(text):
        if word in COMMON_WORDS or len(word) < 3:
            continue
        counts[word] = counts.get(word, 0) + 1
    keywords = [
        word
        for word, _count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]
    if keywords:
        return keywords
    return dedupe_text([content.title or "", *content.bullets])[:limit]


def build_risk_summary(content: ExtractedCompetitorContent) -> list[str]:
    """Flag common risky phrases from competitor public copy."""
    text = " ".join(
        item
        for item in [content.title, *content.bullets, content.description_text]
        if item
    ).lower()
    return [term for term in RISK_TERMS if term in text]


def estimate_extraction_confidence(content: ExtractedCompetitorContent) -> float:
    """Estimate confidence from how much structured content was extracted."""
    score = 0.0
    if content.title:
        score += 0.35
    if content.bullets:
        score += min(0.4, len(content.bullets) * 0.08)
    if content.description_text:
        score += 0.25
    return round(min(score, 1.0), 2)


def infer_visible_specifications(content: ExtractedCompetitorContent) -> list[str]:
    """Extract simple visible specs such as dimensions, pack counts, and materials."""
    text = " ".join([content.title or "", *content.bullets, content.description_text or ""])
    patterns = [
        r"\b\d+(?:\.\d+)?\s?(?:inch|inches|in|ft|feet|cm|mm|oz|lb|lbs|kg|g|ml|l)\b",
        r"\bpack of \d+\b",
        r"\b\d+\s?pack\b",
        r"\b(?:stainless steel|cotton|plastic|silicone|aluminum|wood|leather|glass)\b",
    ]
    specs: list[str] = []
    for pattern in patterns:
        specs.extend(match.group(0) for match in re.finditer(pattern, text, flags=re.I))
    return dedupe_text(specs)[:20]


def infer_attribute_terms(content: ExtractedCompetitorContent) -> list[str]:
    """Infer common attribute terms from visible text."""
    text = " ".join([content.title or "", *content.bullets, content.description_text or ""]).lower()
    attributes = []
    for term in (
        "waterproof",
        "portable",
        "adjustable",
        "rechargeable",
        "lightweight",
        "heavy duty",
        "stainless steel",
        "silicone",
        "cotton",
        "non-slip",
        "foldable",
        "wireless",
    ):
        if term in text:
            attributes.append(term)
    return attributes


def build_long_tail_keywords(content: ExtractedCompetitorContent) -> list[str]:
    """Extract simple long-tail phrases from title and bullets."""
    values = [content.title or "", *content.bullets[:5]]
    phrases: list[str] = []
    for value in values:
        words = [word for word in re_words(value.lower()) if word not in COMMON_WORDS]
        for index in range(max(len(words) - 2, 0)):
            phrases.append(" ".join(words[index : index + 3]))
    return dedupe_text(phrases)[:12]


def pick_terms_by_markers(content: ExtractedCompetitorContent, markers: list[str]) -> list[str]:
    """Pick short phrases that contain common scenario or audience markers."""
    values = [content.title or "", *content.bullets, content.description_text or ""]
    phrases = []
    marker_set = {marker.lower() for marker in markers}
    for value in values:
        chunks = re.split(r"[,.;:|()\[\]-]+", value)
        for chunk in chunks:
            cleaned = clean_text(chunk)
            if not cleaned or len(cleaned) > 80:
                continue
            lowered = cleaned.lower()
            if any(marker in lowered for marker in marker_set):
                phrases.append(cleaned)
    return dedupe_text(phrases)[:10]


def infer_pain_points(content: ExtractedCompetitorContent) -> list[str]:
    """Infer pain-point language from common terms."""
    text = " ".join([content.title or "", *content.bullets, content.description_text or ""]).lower()
    pain_points = []
    for term in ("mess", "pain", "scratch", "leak", "odor", "noise", "clutter", "slip", "break"):
        if term in text:
            pain_points.append(term)
    return pain_points


def infer_tone(content: ExtractedCompetitorContent) -> str:
    """Infer a coarse copy tone from extracted text."""
    text = " ".join([content.title or "", *content.bullets, content.description_text or ""]).lower()
    if any(term in text for term in ("luxury", "premium", "elegant")):
        return "premium"
    if any(term in text for term in ("professional", "commercial", "industrial")):
        return "professional"
    if any(term in text for term in ("family", "kids", "home")):
        return "family-oriented"
    return "functional"


def infer_title_pattern(title: str | None) -> str:
    """Classify a title pattern without preserving competitor copy."""
    if not title:
        return "unknown"
    has_brand_like_prefix = bool(re.match(r"^[A-Z][A-Za-z0-9&' -]{1,30}\s+", title))
    has_specs = bool(infer_visible_specifications(ExtractedCompetitorContent(title, [], None, "")))
    parts = ["brand/keyword lead" if has_brand_like_prefix else "keyword lead"]
    if has_specs:
        parts.append("visible specs")
    if "," in title:
        parts.append("comma-separated attributes")
    return " + ".join(parts)


def infer_bullet_pattern(bullets: list[str]) -> str:
    """Classify common bullet style."""
    if not bullets:
        return "unknown"
    avg_len = sum(len(item) for item in bullets) / len(bullets)
    if avg_len > 180:
        return "long benefit-led bullets"
    if avg_len > 90:
        return "balanced feature-benefit bullets"
    return "short feature bullets"


def infer_information_density(content: ExtractedCompetitorContent) -> str:
    """Classify information density from extracted text length."""
    length = len(" ".join([content.title or "", *content.bullets, content.description_text or ""]))
    if length > 2500:
        return "high"
    if length > 900:
        return "medium"
    return "low"


def build_evidence(content: ExtractedCompetitorContent) -> list[dict[str, Any]]:
    """Build traceable evidence snippets for analysis fields."""
    evidence = []
    if content.title:
        evidence.append({"field": "title", "snippet": content.title[:240]})
    for index, bullet in enumerate(content.bullets[:5], start=1):
        evidence.append({"field": f"bullet_{index}", "snippet": bullet[:240]})
    if content.description_text:
        evidence.append({"field": "description", "snippet": content.description_text[:240]})
    return evidence


def build_comparison_matrix(summaries: list[CompetitorSummary]) -> list[dict[str, Any]]:
    """Build a row-per-competitor comparison matrix."""
    rows = []
    for summary in summaries:
        analysis = summary.analysis_result if isinstance(summary.analysis_result, dict) else {}
        keyword_analysis = analysis.get("keyword_analysis", {})
        rows.append(
            {
                "competitor_input_id": summary.competitor_input_id,
                "title": summary.title,
                "features": summary.feature_summary or [],
                "keywords": summary.keyword_summary or [],
                "risk_terms": summary.risk_summary or [],
                "attributes": keyword_analysis.get("attributes", [])
                if isinstance(keyword_analysis, dict)
                else [],
                "scenarios": keyword_analysis.get("scenarios", [])
                if isinstance(keyword_analysis, dict)
                else [],
            }
        )
    return rows


def build_aggregate_differentiation_opportunities(
    brief: ProductBrief,
    common_features: list[str],
    common_keywords: list[str],
    common_risks: list[str],
) -> list[str]:
    """Build actionable differentiation opportunities for generation."""
    opportunities = []
    if common_features:
        opportunities.append(
            "Cover common category expectations, then differentiate with verified Brief facts."
        )
    if brief.core_features:
        opportunities.append(
            "Prioritize product-specific core features from the Brief over generic competitor claims."
        )
    if common_keywords:
        opportunities.append(
            "Use shared competitor keywords as SEO signals while writing original copy."
        )
    if common_risks:
        opportunities.append(
            "Avoid risky competitor claims unless the user provides verifiable evidence."
        )
    return opportunities


def build_positioning_strategy(brief: ProductBrief, common_features: list[str]) -> str:
    """Summarize recommended positioning for generation."""
    product_name = brief.product_name or "the product"
    if brief.core_features:
        return (
            f"Position {product_name} around verified Brief features while covering "
            "the category expectations found in competitor listings."
        )
    if common_features:
        return (
            f"Position {product_name} against common category expectations and ask for "
            "more verified differentiators before making strong claims."
        )
    return f"Position {product_name} from the Brief; competitor evidence is limited."


def infer_missing_user_facts(brief: ProductBrief) -> list[str]:
    """List facts that should be confirmed before using strong claims."""
    missing = []
    if not brief.materials:
        missing.append("materials")
    if not brief.size_info:
        missing.append("size_info")
    if not brief.core_features:
        missing.append("core_features")
    if not brief.target_audience:
        missing.append("target_audience")
    return missing


def flatten_text_values(values: Any) -> list[str]:
    """Flatten strings, lists, and shallow dict values into text values."""
    flattened: list[str] = []
    if values is None:
        return flattened
    iterable = values if isinstance(values, list) else [values]
    for value in iterable:
        if isinstance(value, str) and value.strip():
            flattened.append(value.strip())
        elif isinstance(value, list):
            flattened.extend(flatten_text_values(value))
        elif isinstance(value, dict):
            flattened.extend(flatten_text_values(list(value.values())))
    return flattened


def most_common_values(values: list[str], *, limit: int) -> list[str]:
    """Return common normalized values while preserving readable text."""
    normalized_to_value: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for value in values:
        normalized = clean_text(str(value)).lower()
        if not normalized:
            continue
        normalized_to_value.setdefault(normalized, clean_text(str(value)))
        counts[normalized] += 1
    return [normalized_to_value[value] for value, _count in counts.most_common(limit)]


def dedupe_text(values: list[str]) -> list[str]:
    """Deduplicate text values case-insensitively."""
    seen = set()
    result = []
    for value in values:
        cleaned = clean_text(str(value))
        normalized = cleaned.lower()
        if not cleaned or normalized in seen:
            continue
        seen.add(normalized)
        result.append(cleaned)
    return result


def re_words(text: str) -> list[str]:
    """Tokenize text into simple alphanumeric words."""
    return [match.group(0) for match in re.finditer(r"[a-z0-9]+", text)]


def write_competitor_snapshot(competitor_input_id: str, html: str) -> str:
    """Write raw competitor HTML to local storage for traceability."""
    directory = COMPETITOR_SNAPSHOT_DIR / competitor_input_id
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{uuid4().hex}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
