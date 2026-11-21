import asyncio
import json
from datetime import UTC, date, datetime

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select

from app.api.deps import DB, CurrentUser
from app.api.serializers import job_dict, project_dict
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import bad_request, not_found
from app.core.permissions import project_access, require_global, visible_projects_query
from app.models.config import (
    CompanyRevision,
    ProductRevision,
    RedlineRule,
    Template,
    TemplateRevision,
)
from app.models.project import (
    Job,
    Project,
    ProjectAttachment,
    ProjectConfigRef,
    ProjectMember,
)
from app.models.section import ProjectFact
from app.models.tender import TenderDocument
from app.models.user import User
from app.schemas.project import MemberCreate, MemberPatch, ProjectAction, ProjectCreate
from app.services.audit import record_activity
from app.services.files.store import FileStore, validate_signature
from app.services.persistence import commit, model_dict
from app.services.workspace.state import check_project_version, touch_project
from app.services.workspace.view import workspace_view
from app.workers.queue import enqueue

router = APIRouter(tags=["projects"])


@router.post("/projects", status_code=201)
def create_project(payload: ProjectCreate, db: DB, user: CurrentUser):
    require_global(user, "editor")
    company = db.get(CompanyRevision, payload.company_revision_id)
    product = db.get(ProductRevision, payload.product_revision_id)
    template = db.get(TemplateRevision, payload.template_revision_id)
    if not all((company, product, template)) or any(
        item.status != "published" for item in (company, product, template)
    ):
        raise bad_request("只能使用已发布的企业、产品和模板修订", code="unpublished_config")
    template_identity = db.get(Template, template.template_id)
    if template_identity.status == "archived":
        raise bad_request("模板已归档", code="unpublished_config")
    if payload.source_project_id:
        project_access(db, payload.source_project_id, user, "read")
    record = Project(
        **payload.model_dump(
            exclude={
                "company_revision_id",
                "product_revision_id",
                "template_revision_id",
                "package_name",
            }
        ),
        owner_id=user.id,
    )
    db.add(record)
    db.flush()
    redlines = db.scalars(
        select(RedlineRule).where(
            RedlineRule.status == "published",
            ((RedlineRule.scope_type == "company") & (RedlineRule.scope_id == company.company_id))
            | (
                (RedlineRule.scope_type == "product") & (RedlineRule.scope_id == product.product_id)
            ),
        )
    ).all()
    refs = ProjectConfigRef(
        project_id=record.id,
        company_revision_id=company.id,
        product_revision_id=product.id,
        template_revision_id=template.id,
        redline_rule_ids_json=[rule.id for rule in redlines],
    )
    db.add(refs)
    db.add(ProjectMember(project_id=record.id, user_id=user.id, project_role="editor"))
    for key, value in company.fields_json.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            db.add(
                ProjectFact(
                    project_id=record.id,
                    fact_key=key,
                    value_json=value,
                    value_type="number"
                    if isinstance(value, (int, float))
                    else "boolean"
                    if isinstance(value, bool)
                    else "string",
                    source_type="company",
                    source_id=company.id,
                )
            )
    record_activity(
        db,
        user.id,
        "project.created",
        "project",
        record.id,
        record.id,
        {"config_refs": model_dict(refs)},
    )
    commit(db)
    return project_dict(db, record)


@router.get("/projects")
def list_projects(
    db: DB,
    user: CurrentUser,
    keyword: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int | None = None,
):
    statement = visible_projects_query(user)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        statement = statement.where(
            or_(
                Project.name.ilike(pattern),
                Project.code.ilike(pattern),
                Project.customer_name.ilike(pattern),
            )
        )
    if status:
        statement = statement.where(Project.status == status)
    total = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    statement = statement.order_by(Project.created_at.desc())
    if page_size is not None:
        page = max(1, page)
        page_size = min(100, max(1, page_size))
        records = db.scalars(statement.offset((page - 1) * page_size).limit(page_size)).all()
        return {
            "items": [project_dict(db, record) for record in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }
    records = db.scalars(statement).all()
    return [project_dict(db, record) for record in records]


@router.get("/projects/{project_id}")
def get_project(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    return project_dict(db, project)


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(project_id: str, payload: MemberCreate, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, payload.version)
    member_user = db.get(User, payload.user_id)
    if member_user is None or not member_user.active:
        raise not_found("用户")
    if db.get(ProjectMember, {"project_id": project.id, "user_id": payload.user_id}):
        raise bad_request("用户已是项目成员", code="member_exists")
    record = ProjectMember(project_id=project.id, **payload.model_dump(exclude={"version"}))
    db.add(record)
    touch_project(db, project)
    commit(db)
    return model_dict(record)


@router.patch("/projects/{project_id}/members/{user_id}")
def patch_member(project_id: str, user_id: str, payload: MemberPatch, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, payload.version)
    record = db.get(ProjectMember, {"project_id": project.id, "user_id": user_id})
    if record is None:
        raise not_found("项目成员")
    if user_id == project.owner_id and payload.project_role != "editor":
        raise bad_request("项目所有者必须保留编辑角色")
    record.project_role = payload.project_role
    touch_project(db, project)
    commit(db)
    return model_dict(record)


@router.post("/projects/{project_id}/tender-documents", status_code=201)
async def upload_tender(
    project_id: str,
    db: DB,
    user: CurrentUser,
    file: UploadFile = File(...),
    document_type: str = Form("tender"),
    version: int | None = Form(None),
):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, version)
    data = await file.read(get_settings().max_upload_bytes + 1)
    mime = validate_signature(file.filename or "", file.content_type or "", data)
    if (
        mime == "application/pdf"
        and not (file.filename or "").lower().endswith(".pdf")
        or mime != "application/pdf"
        and not (file.filename or "").lower().endswith(".docx")
    ):
        raise bad_request("招标文档仅支持 DOCX 和 PDF", code="unsupported_file_type")
    stored = FileStore().save(db, data, file.filename or "tender", mime, user.id)
    existing = db.scalar(
        select(TenderDocument).where(
            TenderDocument.project_id == project.id, TenderDocument.sha256 == stored.sha256
        )
    )
    if existing:
        db.rollback()
        return model_dict(existing)
    record = TenderDocument(
        project_id=project.id, file_id=stored.id, document_type=document_type, sha256=stored.sha256
    )
    db.add(record)
    if project.status == "draft":
        project.status = "uploaded"
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "tender.uploaded",
        "tender_document",
        record.id,
        project.id,
        {"sha256": stored.sha256, "size": stored.size},
    )
    commit(db)
    return model_dict(record)


@router.post("/projects/{project_id}/attachments", status_code=201)
async def upload_project_attachment(
    project_id: str,
    db: DB,
    user: CurrentUser,
    file: UploadFile = File(...),
    attachment_type: str = Form("supporting"),
    valid_to: date | None = Form(None),
    version: int | None = Form(None),
):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, version)
    data = await file.read(get_settings().max_upload_bytes + 1)
    mime = validate_signature(file.filename or "", file.content_type or "", data)
    if mime not in {"application/pdf", "image/png", "image/jpeg"}:
        raise bad_request("项目附件仅支持 PDF、PNG 和 JPEG", code="unsupported_file_type")
    stored = FileStore().save(db, data, file.filename or "attachment", mime, user.id)
    existing_attachment = db.scalar(
        select(ProjectAttachment).where(
            ProjectAttachment.project_id == project.id,
            ProjectAttachment.file_id == stored.id,
        )
    )
    if existing_attachment:
        return {
            **model_dict(existing_attachment),
            "original_name": stored.original_name,
            "mime_type": stored.mime_type,
            "size": stored.size,
            "sha256": stored.sha256,
        }
    record = ProjectAttachment(
        project_id=project.id,
        file_id=stored.id,
        attachment_type=attachment_type,
        uploaded_by=user.id,
        valid_to=valid_to,
    )
    db.add(record)
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "project.attachment_uploaded",
        "project_attachment",
        record.id,
        project.id,
        {"file_id": stored.id, "sha256": stored.sha256},
    )
    commit(db)
    return {
        **model_dict(record),
        "original_name": stored.original_name,
        "mime_type": stored.mime_type,
        "size": stored.size,
        "sha256": stored.sha256,
    }


@router.post("/projects/{project_id}:parse", status_code=202)
def parse(project_id: str, payload: ProjectAction, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    if payload.version != 1:
        check_project_version(project, payload.version)
    document = (
        db.get(TenderDocument, payload.document_id)
        if payload.document_id
        else db.scalar(
            select(TenderDocument)
            .where(TenderDocument.project_id == project.id)
            .order_by(TenderDocument.created_at.desc())
        )
    )
    if document is None or document.project_id != project.id:
        raise bad_request("请先上传招标文档", code="document_required")
    if document.status == "parsed":
        return {
            "job_id": None,
            "task_id": None,
            "tasks": [],
            "status": "parsed",
            "document_id": document.id,
        }
    job = Job(
        project_id=project.id,
        kind="parse",
        result_json={"document_id": document.id, "actor_id": user.id},
    )
    project.status = "parsing"
    db.add(job)
    commit(db)
    enqueue(job.id)
    db.refresh(job)
    serialized = job_dict(job)
    return {
        **serialized,
        "job_id": job.id,
        "task_id": job.id,
        "tasks": [serialized],
    }


@router.post("/tender-documents/{document_id}:confirm")
def confirm_document(document_id: str, payload: ProjectAction, db: DB, user: CurrentUser):
    document = db.get(TenderDocument, document_id)
    if document is None:
        raise not_found("招标文档")
    project, _ = project_access(db, document.project_id, user, "review")
    check_project_version(project, payload.version)
    if document.status != "parsed":
        raise bad_request("文档尚未解析成功", code="invalid_document_state")
    document.user_confirmed = True
    documents = db.scalars(
        select(TenderDocument).where(
            TenderDocument.project_id == project.id, TenderDocument.status == "parsed"
        )
    ).all()
    project.parse_confirmed = all(item.user_confirmed for item in documents)
    touch_project(db, project)
    commit(db)
    return model_dict(document)


@router.get("/tender-documents/{document_id}/anchors/{anchor_key}")
def read_anchor(document_id: str, anchor_key: str, db: DB, user: CurrentUser):
    from app.models.tender import StoredFile, TenderBlock, TenderOutline

    document = db.get(TenderDocument, document_id)
    if document is None:
        raise not_found("招标文档")
    project_access(db, document.project_id, user)
    block = db.scalar(
        select(TenderBlock).where(
            TenderBlock.document_id == document.id, TenderBlock.anchor_key == anchor_key
        )
    )
    if block is None:
        raise not_found("原文锚点")
    stored = db.get(StoredFile, document.file_id)
    outlines = db.scalars(
        select(TenderOutline).where(TenderOutline.document_id == document.id)
    ).all()
    outline = next(
        (item for item in outlines if item.source_start_anchor == block.anchor_key), None
    )
    return {
        **model_dict(block),
        "document_name": stored.original_name if stored else None,
        "outline_title": outline.title if outline else None,
    }


@router.get("/projects/{project_id}/workspace")
def workspace(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    return workspace_view(db, project)


@router.get("/projects/{project_id}/events")
async def events(project_id: str, request: Request, db: DB, user: CurrentUser):
    project_access(db, project_id, user)

    async def stream():
        last_payload = None
        while True:
            if await request.is_disconnected():
                break
            with SessionLocal() as event_db:
                jobs = event_db.scalars(
                    select(Job)
                    .where(Job.project_id == project_id)
                    .order_by(Job.created_at.desc())
                    .limit(20)
                ).all()
                payload = [job_dict(job) for job in jobs]
            encoded = json.dumps(payload, ensure_ascii=False)
            if encoded != last_payload:
                event_id = datetime.now(UTC).timestamp()
                yield f"id: {event_id}\nevent: task\ndata: {encoded}\n\n"
                yield f"id: {event_id}\nevent: jobs\ndata: {encoded}\n\n"
                last_payload = encoded
            else:
                yield ": heartbeat\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
