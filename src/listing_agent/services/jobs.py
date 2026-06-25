from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from listing_agent.core.logging import get_logger
from listing_agent.core.time import now_app_timezone
from listing_agent.db.session import get_session_factory
from listing_agent.models.v1_data import CompetitorInput, Job
from listing_agent.services.competitor_analysis import (
    CompetitorAnalysisService,
    CompetitorInputNotFoundError,
)

logger = get_logger(__name__)


class JobNotFoundError(Exception):
    """Raised when a job ID does not exist."""


class JobQueueService:
    """Lightweight database-backed task queue for V1 background work."""

    async def get_job(self, session: AsyncSession, job_id: str) -> Job:
        """Load one job by ID."""
        result = await session.execute(select(Job).where(Job.id == job_id))
        job = result.scalar_one_or_none()
        if job is None:
            raise JobNotFoundError(job_id)
        return job

    async def enqueue_competitor_analysis(
        self,
        session: AsyncSession,
        competitor_input_id: str,
    ) -> Job:
        """Create or reuse the competitor analysis job for one competitor input."""
        existing_job = await self.get_competitor_analysis_job(session, competitor_input_id)
        if existing_job is not None:
            return existing_job

        job = Job(
            job_type="competitor_analysis",
            related_id=competitor_input_id,
            status="queued",
            payload={"competitor_input_id": competitor_input_id},
        )
        session.add(job)
        competitor_input = await self._get_competitor_input(session, competitor_input_id)
        if competitor_input is not None:
            competitor_input.status = "queued"
        await session.commit()
        await session.refresh(job)
        logger.info(
            "job_queued job_id=%s job_type=%s related_id=%s",
            job.id,
            job.job_type,
            job.related_id,
        )
        return job

    async def get_competitor_analysis_job(
        self,
        session: AsyncSession,
        competitor_input_id: str,
    ) -> Job | None:
        """Return the latest analysis job for a competitor input when one already exists."""
        result = await session.execute(
            select(Job)
            .where(
                Job.job_type == "competitor_analysis",
                Job.related_id == competitor_input_id,
                Job.status.in_(["queued", "running", "completed"]),
            )
            .order_by(Job.created_at.desc())
        )
        return result.scalars().first()

    async def _get_competitor_input(
        self,
        session: AsyncSession,
        competitor_input_id: str,
    ) -> CompetitorInput | None:
        result = await session.execute(
            select(CompetitorInput).where(CompetitorInput.id == competitor_input_id)
        )
        return result.scalar_one_or_none()

    async def _update_competitor_input_status(
        self,
        session: AsyncSession,
        competitor_input_id: str,
        status: str,
    ) -> None:
        competitor_input = await self._get_competitor_input(session, competitor_input_id)
        if competitor_input is not None:
            competitor_input.status = status

    async def run_competitor_analysis_job(self, job_id: str, competitor_input_id: str) -> None:
        """Execute a queued competitor analysis job and update its persisted status."""
        async with get_session_factory()() as session:
            job = await self.get_job(session, job_id)
            job.status = "running"
            job.started_at = now_app_timezone()
            await self._update_competitor_input_status(session, competitor_input_id, "running")
            await session.commit()
            logger.info("job_started job_id=%s job_type=%s", job.id, job.job_type)

        try:
            async with get_session_factory()() as session:
                job = await self.get_job(session, job_id)
                execution_job, summary = await CompetitorAnalysisService().analyze_competitor(
                    session,
                    competitor_input_id,
                    job,
                )
        except CompetitorInputNotFoundError:
            async with get_session_factory()() as session:
                job = await self.get_job(session, job_id)
                job.status = "failed"
                job.error_message = "competitor input not found"
                job.finished_at = now_app_timezone()
                await self._update_competitor_input_status(session, competitor_input_id, "failed")
                await session.commit()
                logger.warning("job_failed job_id=%s job_type=%s", job.id, job.job_type)
            return
        except Exception as exc:
            async with get_session_factory()() as session:
                job = await self.get_job(session, job_id)
                job.status = "failed"
                job.error_message = str(exc)
                job.finished_at = now_app_timezone()
                await self._update_competitor_input_status(session, competitor_input_id, "failed")
                await session.commit()
                logger.exception("job_failed job_id=%s job_type=%s", job.id, job.job_type)
            return

        async with get_session_factory()() as session:
            job = await self.get_job(session, job_id)
            job.status = "completed" if summary is not None else "failed"
            job.result_summary = (
                "Competitor analysis completed."
                if summary is not None
                else "Competitor analysis failed."
            )
            job.error_message = None if summary is not None else execution_job.error_message
            job.finished_at = now_app_timezone()
            await self._update_competitor_input_status(
                session,
                competitor_input_id,
                "completed" if summary is not None else "failed",
            )
            payload = dict(job.payload or {})
            payload["execution_job_id"] = execution_job.id
            payload["summary_id"] = summary.id if summary is not None else None
            job.payload = payload
            await session.commit()
            logger.info(
                "job_finished job_id=%s job_type=%s status=%s",
                job.id,
                job.job_type,
                job.status,
            )
