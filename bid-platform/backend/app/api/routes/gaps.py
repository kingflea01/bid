import copy
import json

from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.api.deps import DB, CurrentUser
from app.api.routes.sections import validate_attachment_access
from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import AppError, bad_request, not_found
from app.core.permissions import project_access
from app.models.asset import AssetRevision
from app.models.project import ProjectAttachment
from app.models.section import Gap, ProjectSection, ProjectSectionRevision
from app.models.tender import StoredFile
from app.schemas.section import GapResolve
from app.services.audit import record_activity
from app.services.files.store import FileStore, validate_signature
from app.services.persistence import commit, model_dict
from app.services.workspace.content import placeholders
from app.services.workspace.state import check_project_version, touch_project
from app.services.workspace.versions import create_revision, validate_tender_references

router = APIRouter(prefix="/gaps", tags=["gaps"])


async def resolution_payload(request: Request) -> tuple[GapResolve, object | None]:
    upload = None
    if request.headers.get("content-type", "").startswith("application/json"):
        raw = await request.json()
        data = raw.get("resolution_json", raw)
        if raw.get("version") is not None and "version" not in data:
            data["version"] = raw["version"]
    else:
        form = await request.form()
        raw = form.get("resolution_json")
        if raw:
            try:
                data = json.loads(str(raw))
            except json.JSONDecodeError as exc:
                raise bad_request("resolution_json 不是有效 JSON") from exc
        else:
            data = {key: value for key, value in form.items() if key != "file"}
        upload = form.get("file")
        if form.get("version") is not None:
            data["version"] = form["version"]
    try:
        return GapResolve.model_validate(data), upload
    except ValidationError as exc:
        details = [
            {"loc": list(error["loc"]), "message": error["msg"], "type": error["type"]}
            for error in exc.errors()
        ]
        raise AppError(422, "validation_error", "请求参数校验失败", details) from exc


@router.post("/{gap_id}:resolve")
async def resolve(gap_id: str, request: Request, db: DB, user: CurrentUser):
    payload, upload = await resolution_payload(request)
    gap = db.get(Gap, gap_id)
    if gap is None:
        raise not_found("缺口")
    project, _ = project_access(db, gap.project_id, user, "edit")
    check_project_version(project, payload.version)
    if gap.status != "open":
        raise bad_request("缺口已关闭", code="invalid_gap_state")
    resolution_type = "manual" if payload.resolution_type == "text" else payload.resolution_type
    file_id = payload.file_id or payload.attachment_id
    if upload is not None:
        data = await upload.read(get_settings().max_upload_bytes + 1)
        mime = validate_signature(upload.filename or "", upload.content_type or "", data)
        if mime not in {"application/pdf", "image/png", "image/jpeg"}:
            raise bad_request("项目附件仅支持 PDF、PNG 和 JPEG", code="unsupported_file_type")
        stored_upload = FileStore().save(db, data, upload.filename or "attachment", mime, user.id)
        from sqlalchemy import select

        existing_link = db.scalar(
            select(ProjectAttachment).where(
                ProjectAttachment.project_id == project.id,
                ProjectAttachment.file_id == stored_upload.id,
            )
        )
        if existing_link is None:
            db.add(
                ProjectAttachment(
                    project_id=project.id,
                    file_id=stored_upload.id,
                    attachment_type=gap.gap_type,
                    uploaded_by=user.id,
                )
            )
        file_id = stored_upload.id
    resolution = {
        "resolution_type": payload.resolution_type,
        "note": payload.note,
        "project_version": payload.version,
    }
    section = db.get(ProjectSection, gap.section_id) if gap.section_id else None
    current = (
        db.get(ProjectSectionRevision, section.selected_revision_id)
        if section and section.selected_revision_id
        else None
    )
    if resolution_type == "asset":
        if not section or not payload.asset_revision_id:
            raise bad_request("素材解决方式需要章节和素材修订")
        asset_revision = db.get(AssetRevision, payload.asset_revision_id)
        if asset_revision is None or asset_revision.status != "published":
            raise not_found("素材修订")
        validate_tender_references(db, section, asset_revision.content_json)
        create_revision(
            db,
            section,
            asset_revision.content_json,
            "asset",
            user.id,
            source_asset_revision_id=asset_revision.id,
        )
        resolution["asset_revision_id"] = asset_revision.id
    elif resolution_type == "attachment":
        if not section or not file_id:
            raise bad_request("附件解决方式需要章节和文件")
        stored = db.get(StoredFile, file_id)
        if stored is None:
            raise not_found("附件")
        attachment_block = {
            "type": "attachment_ref",
            "file_id": stored.id,
            "name": gap.title.removeprefix("附件："),
        }
        validate_attachment_access(db, section, [attachment_block], user)
        content = copy.deepcopy(current.content_json) if current else []
        replaced = False
        for index, block in enumerate(content):
            if block.get("type") == "placeholder" and (
                block.get("name") == gap.title
                or block.get("label") == gap.title
                or block.get("text") == f"[[{gap.title}]]"
            ):
                content[index] = attachment_block
                replaced = True
                break
        if not replaced:
            content.append(attachment_block)
        create_revision(db, section, content, "manual", user.id, make_manual_candidate=True)
        resolution["file_id"] = stored.id
        resolution["attachment_id"] = stored.id
    elif current and (
        gap.title in placeholders(current.content_json)
        or gap.title.removeprefix("字段：") in placeholders(current.content_json)
    ):
        raise bad_request(
            "请先编辑正文移除对应占位符，再填写实际解决依据", code="placeholder_still_present"
        )
    gap.status = "resolved"
    gap.resolved_by = user.id
    gap.resolved_at = utcnow()
    gap.resolution_json = resolution
    if section and section.selected_revision_id:
        selected = db.get(ProjectSectionRevision, section.selected_revision_id)
        section.content_status = "gap" if placeholders(selected.content_json) else "ready"
    touch_project(db, project)
    record_activity(db, user.id, "gap.resolved", "gap", gap.id, project.id, resolution)
    commit(db)
    return model_dict(gap)
