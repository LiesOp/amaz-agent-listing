from datetime import datetime

from pydantic import BaseModel


class JobResponse(BaseModel):
    """Public task status response."""

    id: str
    job_type: str
    related_id: str | None
    status: str
    payload: dict | list | None
    result_summary: str | None
    error_message: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
