import logging

from redis import Redis
from rq import Queue

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.project import Job
from app.services.persistence import commit

logger = logging.getLogger(__name__)


def enqueue(job_id: str) -> None:
    settings = get_settings()
    if not settings.synchronous_tasks:
        try:
            redis = Redis.from_url(settings.redis_url)
            rq_job = Queue("default", connection=redis).enqueue(
                "app.workers.tasks.run_job", job_id, job_timeout=900, result_ttl=86400
            )
            with SessionLocal() as db:
                job = db.get(Job, job_id)
                if job:
                    job.rq_job_id = rq_job.id
                    commit(db)
            return
        except Exception as exc:
            logger.error(
                "RQ enqueue unavailable (%s); using synchronous fallback", type(exc).__name__
            )
    from app.workers.tasks import run_job

    run_job(job_id)
