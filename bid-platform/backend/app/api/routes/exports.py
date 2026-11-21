from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import export_dict
from app.core.errors import AppError, not_found
from app.core.permissions import project_access
from app.models.project import Job
from app.models.task import ExportTask
from app.models.tender import StoredFile
from app.schemas.export import ExportCreate
from app.services.files.store import FileStore, safe_export_name
from app.services.persistence import commit
from app.services.workspace.qa import evaluate_snapshot_qa
from app.services.workspace.snapshots import project_snapshot
from app.services.workspace.state import check_project_version
from app.workers.queue import enqueue

router = APIRouter(tags=["exports"])


@router.get("/projects/{project_id}/exports")
def list_exports(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    tasks = db.scalars(
        select(ExportTask)
        .where(ExportTask.project_id == project.id)
        .order_by(ExportTask.created_at.desc())
    ).all()
    return [export_dict(db, task) for task in tasks]


@router.post("/projects/{project_id}/exports", status_code=202)
def create_export(project_id: str, payload: ExportCreate, db: DB, user: CurrentUser):
    action = "review" if payload.export_kind == "formal" else "review_export"
    project, _ = project_access(db, project_id, user, action)
    check_project_version(project, payload.version)
    snapshot = project_snapshot(db, project, payload.snapshot_id)
    qa = evaluate_snapshot_qa(db, project, snapshot, payload.export_kind)
    task = ExportTask(
        project_id=project.id,
        snapshot_id=snapshot.id,
        export_kind=payload.export_kind,
        format=payload.format,
        qa_json=qa,
        created_by=user.id,
    )
    if not qa["passed"]:
        task.status = "blocked"
        task.error_code = "export_blocked"
        db.add(task)
        commit(db)
        raise AppError(
            422, "export_blocked", "正式导出质量门禁未通过", {"export_id": task.id, "qa": qa}
        )
    db.add(task)
    db.flush()
    job = Job(
        project_id=project.id,
        kind="export",
        result_json={"export_task_id": task.id, "include_sources": payload.include_sources},
    )
    db.add(job)
    db.flush()
    task.job_id = job.id
    commit(db)
    enqueue(job.id)
    db.refresh(task)
    return export_dict(db, task)


@router.get("/exports/{export_id}")
def get_export(export_id: str, db: DB, user: CurrentUser):
    task = db.get(ExportTask, export_id)
    if task is None:
        raise not_found("导出任务")
    project_access(db, task.project_id, user)
    return export_dict(db, task)


@router.get("/exports/{export_id}/download")
def download(export_id: str, db: DB, user: CurrentUser):
    task = db.get(ExportTask, export_id)
    if task is None:
        raise not_found("导出任务")
    project_access(db, task.project_id, user, "review" if task.export_kind == "formal" else "read")
    if task.status != "succeeded" or not task.file_id:
        raise AppError(409, "export_not_ready", "导出文件尚未就绪")
    stored = db.get(StoredFile, task.file_id)
    if stored is None:
        raise not_found("导出文件")
    path = FileStore().path_for(stored)
    return FileResponse(
        path,
        filename=safe_export_name(stored.original_name.rsplit(".", 1)[0], task.format),
        media_type=stored.mime_type,
    )
