from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["jobs"])


class JobStatusOut(BaseModel):
    job_id: str
    status: str  # queued | started | finished | failed | not_found
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.get("/jobs/{job_id}", response_model=JobStatusOut)
def get_job_status(job_id: str):
    """Poll the status of a background RQ job by its ID."""
    try:
        import redis as redis_lib
        from rq.job import Job, NoSuchJobError
        from app.core.config import settings

        r = redis_lib.from_url(settings.REDIS_URL)
        try:
            job = Job.fetch(job_id, connection=r)
        except NoSuchJobError:
            return JobStatusOut(job_id=job_id, status="not_found")

        rq_status = job.get_status()
        # rq_status is a JobStatus enum in newer rq; coerce to string
        status_str = rq_status.value if hasattr(rq_status, "value") else str(rq_status)

        result = None
        error = None
        if status_str == "finished":
            result = job.result
        elif status_str == "failed":
            error = str(job.exc_info) if job.exc_info else "Job failed"

        return JobStatusOut(job_id=job_id, status=status_str, result=result, error=error)

    except Exception as exc:
        return JobStatusOut(job_id=job_id, status="error", error=str(exc))
