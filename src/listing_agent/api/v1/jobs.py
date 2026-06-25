from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.db.session import get_db_session
from listing_agent.models.v1_data import Job
from listing_agent.schemas.job import JobResponse
from listing_agent.services.jobs import JobNotFoundError, JobQueueService

router = APIRouter(prefix="/jobs", tags=["jobs"])
job_service = JobQueueService()


def _to_job_response(job: Job) -> JobResponse:
    """Map a persisted Job to the public response contract."""
    return JobResponse(
        id=job.id,
        job_type=job.job_type,
        related_id=job.related_id,
        status=job.status,
        payload=job.payload,
        result_summary=job.result_summary,
        error_message=job.error_message,
        started_at=job.started_at,
        finished_at=job.finished_at,
        created_at=job.created_at,
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    job_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> JobResponse:
    """Return the current status for a queued or completed background task."""
    try:
        job = await job_service.get_job(session, job_id)
    except JobNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="job not found") from exc
    return _to_job_response(job)
