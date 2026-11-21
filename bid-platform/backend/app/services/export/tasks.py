from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import AppError
from app.models.project import Job, Project
from app.models.task import ExportTask
from app.services.export.docx_builder import build_docx
from app.services.export.pdf_builder import convert_docx_to_pdf
from app.services.files.store import FileStore, safe_export_name
from app.services.workspace.qa import evaluate_snapshot_qa
from app.services.workspace.snapshots import project_snapshot


def run_export(db: Session, job: Job) -> dict:
    task = db.scalar(select(ExportTask).where(ExportTask.job_id == job.id))
    if task is None:
        raise ValueError("export task not found")
    task.status = "running"
    db.commit()
    project = db.get(Project, task.project_id)
    snapshot = project_snapshot(db, project, task.snapshot_id)
    qa = evaluate_snapshot_qa(db, project, snapshot, task.export_kind)
    if not qa["passed"]:
        task.status = "blocked"
        task.qa_json = qa
        task.error_code = "export_blocked"
        task.finished_at = utcnow()
        db.commit()
        raise AppError(422, "export_blocked", "正式导出质量门禁未通过", qa)
    include_sources = bool(job.result_json.get("include_sources"))
    data, output_qa = build_docx(db, project, snapshot, task.export_kind, qa, include_sources)
    structural_errors = [
        error for error in output_qa["ooxml_errors"] if not error.endswith("missing_source_blocks")
    ]
    if (
        task.export_kind == "formal"
        and (output_qa["output_placeholders"] or output_qa["ooxml_errors"])
        or structural_errors
    ):
        output_qa["passed"] = False
        output_qa["blockers"].append(
            {
                "code": "output_validation",
                "message": "生成文件仍有占位符或 OOXML 校验异常",
                "entities": output_qa["output_placeholders"] + output_qa["ooxml_errors"],
            }
        )
        task.status = "blocked"
        task.qa_json = output_qa
        task.error_code = "output_validation"
        task.finished_at = utcnow()
        db.commit()
        raise AppError(422, "output_validation", "生成文件未通过导出校验")
    if task.format == "pdf":
        data, pdf_qa = convert_docx_to_pdf(data)
        output_qa["pdf"] = pdf_qa
    original_name = safe_export_name(
        f"{project.code}-snapshot-{snapshot.snapshot_no}-{task.export_kind}", task.format
    )
    stored = FileStore().save(
        db,
        data,
        original_name,
        "application/pdf"
        if task.format == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        task.created_by,
    )
    output_qa["file_sha256"] = stored.sha256
    output_qa["passed"] = True
    task.file_id = stored.id
    task.qa_json = output_qa
    project.status = "completed" if task.export_kind == "formal" else "review"
    task.status = "succeeded"
    task.finished_at = utcnow()
    db.commit()
    return {
        "export_id": task.id,
        "status": task.status,
        "file_id": stored.id,
        "sha256": stored.sha256,
        "qa": output_qa,
    }
