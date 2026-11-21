import logging

from app.core.database import SessionLocal, utcnow
from app.core.errors import AppError
from app.models.project import Job, Project

logger = logging.getLogger(__name__)


def run_job(job_id: str) -> dict:
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job is None:
            raise ValueError("job not found")
        if job.status == "succeeded":
            return job.result_json
        job.status = "running"
        job.started_at = utcnow()
        job.progress = 5
        db.commit()
        try:
            if job.kind == "parse":
                from app.services.projects import parse_project_document

                result = parse_project_document(
                    db,
                    job.project_id,
                    job.result_json["document_id"],
                    job.result_json.get("actor_id"),
                )
            elif job.kind == "ai_analysis":
                from app.services.ai.tasks import run_analysis

                result = run_analysis(db, job)
            elif job.kind == "ai_mapping":
                from app.services.ai.tasks import run_mapping

                result = run_mapping(db, job)
            elif job.kind == "export":
                from app.services.export.tasks import run_export

                result = run_export(db, job)
            else:
                raise ValueError("unsupported job kind")
            job = db.get(Job, job_id)
            project = db.get(Project, job.project_id)
            if project and job.kind == "ai_analysis" and project.status == "analyzing":
                project.status = "workspace"
            job.status = "succeeded"
            job.progress = 100
            job.result_json = result
            job.finished_at = utcnow()
            db.commit()
            return result
        except Exception as exc:
            db.rollback()
            failed = db.get(Job, job_id)
            failed.status = "failed"
            failed.error_code = exc.code if isinstance(exc, AppError) else "job_failed"
            failed.result_json = {
                **failed.result_json,
                "message": exc.message if isinstance(exc, AppError) else "任务执行失败",
            }
            failed.finished_at = utcnow()
            project = db.get(Project, failed.project_id)
            if project and failed.kind == "ai_analysis" and project.status == "analyzing":
                project.status = "workspace"
            elif project and failed.kind == "parse" and project.status == "parsing":
                project.status = "uploaded"
            if failed.kind == "export":
                from sqlalchemy import select

                from app.models.task import ExportTask

                export = db.scalar(select(ExportTask).where(ExportTask.job_id == failed.id))
                if export and export.status == "running":
                    export.status = "failed"
                    export.error_code = failed.error_code
                    export.finished_at = utcnow()
            logger.error("Job %s failed with %s", failed.kind, type(exc).__name__)
            db.commit()
            return failed.result_json
