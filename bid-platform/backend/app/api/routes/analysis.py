from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import job_dict, requirement_dict
from app.core.errors import bad_request
from app.core.permissions import project_access
from app.models.project import Job
from app.models.section import ProjectSection
from app.models.tender import Requirement, TenderDocument
from app.schemas.analysis import AnalyzeRequest, MappingRequest
from app.services.persistence import commit
from app.services.workspace.state import check_project_version
from app.workers.queue import enqueue

router = APIRouter(tags=["analysis"])


def analysis_job_response(job: Job) -> dict:
    serialized = job_dict(job)
    return {
        **serialized,
        "job_id": job.id,
        "task_id": job.id,
        "task_ids": [job.id],
        "tasks": [serialized],
    }


@router.post("/projects/{project_id}:analyze", status_code=202)
def analyze(project_id: str, payload: AnalyzeRequest, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    if payload.version != 1:
        check_project_version(project, payload.version)
    parsed = db.scalar(
        select(TenderDocument.id)
        .where(TenderDocument.project_id == project.id, TenderDocument.status == "parsed")
        .limit(1)
    )
    if not parsed:
        raise bad_request("请先成功解析招标文档", code="document_required")
    active = db.scalar(
        select(Job)
        .where(
            Job.project_id == project.id,
            Job.kind == "ai_analysis",
            Job.status.in_(["queued", "running"]),
        )
        .order_by(Job.created_at.desc())
    )
    if active:
        return analysis_job_response(active)
    job = Job(project_id=project.id, kind="ai_analysis")
    project.status = "analyzing"
    db.add(job)
    commit(db)
    enqueue(job.id)
    db.refresh(job)
    return analysis_job_response(job)


@router.post("/projects/{project_id}:resolve-mapping", status_code=202)
def resolve_mapping(project_id: str, payload: MappingRequest, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, payload.version)
    unresolved = db.scalar(
        select(ProjectSection.id)
        .where(
            ProjectSection.project_id == project.id, ProjectSection.mapping_status == "needs_review"
        )
        .limit(1)
    )
    if not unresolved:
        raise bad_request("当前没有需要 AI 消歧的编排节点", code="no_mapping_ambiguity")
    active = db.scalar(
        select(Job)
        .where(
            Job.project_id == project.id,
            Job.kind == "ai_mapping",
            Job.status.in_(["queued", "running"]),
        )
        .order_by(Job.created_at.desc())
    )
    if active:
        return analysis_job_response(active)
    job = Job(project_id=project.id, kind="ai_mapping")
    db.add(job)
    commit(db)
    enqueue(job.id)
    db.refresh(job)
    return analysis_job_response(job)


@router.get("/projects/{project_id}/requirements")
def requirements(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    documents = db.scalars(
        select(TenderDocument).where(TenderDocument.project_id == project.id)
    ).all()
    records = (
        db.scalars(
            select(Requirement)
            .where(Requirement.document_id.in_([doc.id for doc in documents]))
            .order_by(Requirement.code)
        ).all()
        if documents
        else []
    )
    return [requirement_dict(db, requirement) for requirement in records]
