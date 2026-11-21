from fastapi import APIRouter

from app.api.deps import DB, CurrentUser
from app.api.serializers import job_dict
from app.core.errors import not_found
from app.core.permissions import project_access
from app.models.project import Job

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{job_id}")
def get_task(job_id: str, db: DB, user: CurrentUser):
    job = db.get(Job, job_id)
    if job is None:
        raise not_found("任务")
    if job.project_id:
        project_access(db, job.project_id, user)
    elif user.global_role != "admin":
        raise not_found("任务")
    return job_dict(job)
