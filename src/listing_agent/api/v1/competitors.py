from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import CompetitorAnalysis, CompetitorInput, CompetitorSummary
from listing_agent.schemas.competitor import (
    AggregatedCompetitorAnalysisResponse,
    CompetitorAnalysisListResponse,
    CompetitorImportAnalysisJobResponse,
    CompetitorAnalysisResponse,
    CompetitorImportRequest,
    CompetitorImportResponse,
    CompetitorInputResponse,
    CompetitorSummaryResponse,
)
from listing_agent.services.briefs import BriefNotFoundError
from listing_agent.services.competitor_analysis import (
    CompetitorAggregationError,
    CompetitorAnalysisService,
    CompetitorInputNotFoundError,
)
from listing_agent.services.competitors import (
    CompetitorImportService,
    CompetitorInputValidationError,
)
from listing_agent.services.conversations import ConversationNotFoundError
from listing_agent.services.jobs import JobQueueService

router = APIRouter(prefix="/competitors", tags=["competitors"])
competitor_service = CompetitorImportService()
analysis_service = CompetitorAnalysisService()
job_service = JobQueueService()


def _to_competitor_input_response(item: CompetitorInput) -> CompetitorInputResponse:
    """Map a competitor input ORM row to an API response."""
    return CompetitorInputResponse(
        id=item.id,
        conversation_id=item.conversation_id,
        brief_id=item.brief_id,
        input_type=item.input_type,
        input_value=item.input_value,
        normalized_url=item.normalized_url,
        asin=item.asin,
        status=item.status,
        created_at=item.created_at,
    )


def _to_competitor_summary_response(summary: CompetitorSummary) -> CompetitorSummaryResponse:
    """Map a competitor summary ORM row to an API response."""
    return CompetitorSummaryResponse(
        id=summary.id,
        competitor_input_id=summary.competitor_input_id,
        brief_id=summary.brief_id,
        title=summary.title,
        bullets=summary.bullets,
        description_text=summary.description_text,
        search_terms=summary.search_terms,
        feature_summary=summary.feature_summary,
        keyword_summary=summary.keyword_summary,
        risk_summary=summary.risk_summary,
        raw_content_snapshot=summary.raw_content_snapshot,
        extraction_result=summary.extraction_result,
        analysis_result=summary.analysis_result,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
    )


def _to_aggregated_analysis_response(
    analysis: CompetitorAnalysis,
) -> AggregatedCompetitorAnalysisResponse:
    """Map an aggregated competitor analysis ORM row to an API response."""
    return AggregatedCompetitorAnalysisResponse(
        id=analysis.id,
        brief_id=analysis.brief_id,
        conversation_id=analysis.conversation_id,
        status=analysis.status,
        competitor_count=analysis.competitor_count,
        report=analysis.report,
        action_brief=analysis.action_brief,
        constraints=analysis.constraints,
        error_message=analysis.error_message,
        model_name=analysis.model_name,
        created_at=analysis.created_at,
        updated_at=analysis.updated_at,
    )


@router.post(
    "/import",
    response_model=CompetitorImportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_competitors(
    payload: CompetitorImportRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorImportResponse:
    """Validate and save competitor URL or ASIN inputs."""
    try:
        items = await competitor_service.import_competitors(session, payload)
    except ConversationNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="conversation not found",
        ) from exc
    except BriefNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="brief not found",
        ) from exc
    except CompetitorInputValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    analysis_jobs = []
    for item in items:
        job = await job_service.enqueue_competitor_analysis(session, item.id)
        analysis_jobs.append(
            CompetitorImportAnalysisJobResponse(
                competitor_input_id=item.id,
                job_id=job.id,
                status=job.status,
            )
        )
        if job.status == "queued":
            background_tasks.add_task(
                job_service.run_competitor_analysis_job,
                job.id,
                item.id,
            )

    return CompetitorImportResponse(
        job_id=analysis_jobs[0].job_id,
        status="queued",
        imported_count=len(items),
        items=[_to_competitor_input_response(item) for item in items],
        analysis_jobs=analysis_jobs,
    )


@router.get("/analyses", response_model=CompetitorAnalysisListResponse)
async def list_competitor_analyses(
    brief_id: str | None = None,
    conversation_id: str | None = None,
    status_filter: str | None = None,
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorAnalysisListResponse:
    """Return completed aggregated competitor analyses for the read-only menu."""
    statement = select(CompetitorAnalysis).order_by(CompetitorAnalysis.updated_at.desc())
    if brief_id:
        statement = statement.where(CompetitorAnalysis.brief_id == brief_id)
    if conversation_id:
        statement = statement.where(CompetitorAnalysis.conversation_id == conversation_id)
    if status_filter:
        statement = statement.where(CompetitorAnalysis.status == status_filter)
    result = await session.execute(statement)
    return CompetitorAnalysisListResponse(
        items=[_to_aggregated_analysis_response(item) for item in result.scalars().all()]
    )


@router.get("/analyses/{analysis_id}", response_model=AggregatedCompetitorAnalysisResponse)
async def get_competitor_analysis(
    analysis_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AggregatedCompetitorAnalysisResponse:
    """Return one aggregated competitor analysis report."""
    result = await session.execute(
        select(CompetitorAnalysis).where(CompetitorAnalysis.id == analysis_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="competitor analysis not found",
        )
    return _to_aggregated_analysis_response(analysis)


@router.get("/by-brief/{brief_id}/analysis", response_model=AggregatedCompetitorAnalysisResponse)
async def get_competitor_analysis_by_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AggregatedCompetitorAnalysisResponse:
    """Return the aggregated competitor analysis report for one Brief."""
    result = await session.execute(
        select(CompetitorAnalysis).where(CompetitorAnalysis.brief_id == brief_id)
    )
    analysis = result.scalar_one_or_none()
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="competitor analysis not found",
        )
    return _to_aggregated_analysis_response(analysis)


@router.post("/by-brief/{brief_id}/aggregate-analysis", response_model=AggregatedCompetitorAnalysisResponse)
async def aggregate_competitor_analysis_by_brief(
    brief_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> AggregatedCompetitorAnalysisResponse:
    """Manually trigger final LLM aggregation for all completed competitor analyses."""
    try:
        analysis = await analysis_service.aggregate_competitor_analysis(session, brief_id)
    except CompetitorAggregationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="competitor analysis not found",
        )
    return _to_aggregated_analysis_response(analysis)


@router.post("/{competitor_input_id}/analyze", response_model=CompetitorAnalysisResponse)
async def analyze_competitor(
    competitor_input_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorAnalysisResponse:
    """Fetch public competitor content and save a structured summary."""
    try:
        job, summary = await analysis_service.analyze_competitor(session, competitor_input_id)
    except CompetitorInputNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="competitor input not found",
        ) from exc

    return CompetitorAnalysisResponse(
        job_id=job.id,
        status=job.status,
        competitor_input_id=competitor_input_id,
        summary=_to_competitor_summary_response(summary) if summary is not None else None,
        error_message=job.error_message,
    )


@router.get("/{competitor_input_id}/summary", response_model=CompetitorSummaryResponse)
async def get_competitor_summary(
    competitor_input_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> CompetitorSummaryResponse:
    """Return the persisted structured analysis result for one competitor input."""
    summary = await _get_summary_by_input_id(session, competitor_input_id)
    if summary is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="competitor summary not found",
        )
    return _to_competitor_summary_response(summary)


async def _get_summary_by_input_id(
    session: AsyncSession,
    competitor_input_id: str,
) -> CompetitorSummary | None:
    result = await session.execute(
        select(CompetitorSummary).where(
            CompetitorSummary.competitor_input_id == competitor_input_id
        )
    )
    return result.scalar_one_or_none()
