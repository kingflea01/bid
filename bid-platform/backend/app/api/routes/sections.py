from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import revision_dict
from app.core.errors import bad_request, conflict, not_found
from app.core.permissions import project_access
from app.models.asset import AssetAttachment
from app.models.project import ProjectAttachment
from app.models.section import (
    Gap,
    ProjectSection,
    ProjectSectionRevision,
    SectionDependency,
)
from app.models.tender import StoredFile, TenderDocument
from app.schemas.section import (
    ConfirmSection,
    SectionMove,
    SectionPatch,
    SectionRevisionCreate,
    SelectVersion,
)
from app.services.audit import record_activity
from app.services.persistence import commit, model_dict
from app.services.workspace.content import placeholders
from app.services.workspace.state import check_project_version, touch_project
from app.services.workspace.tree import move_section
from app.services.workspace.versions import (
    create_revision,
    find_section_candidate,
    select_candidate,
    validate_tender_references,
)

router = APIRouter(prefix="/sections", tags=["sections"])


def section_context(db: DB, section_id: str, user: CurrentUser, action: str = "read"):
    section = db.get(ProjectSection, section_id)
    if section is None:
        raise not_found("章节")
    project, _ = project_access(db, section.project_id, user, action)
    return section, project


def check_section_version(section: ProjectSection, expected: int | None) -> None:
    if expected is not None and section.version != expected:
        raise conflict(
            "章节已被其他用户修改，请刷新后重试",
            {"expected_version": expected, "current_version": section.version},
        )


def validate_attachment_access(db: DB, section: ProjectSection, content, user) -> None:
    file_ids = {
        block.get("file_id") or block.get("attachment_id")
        for block in content
        if block.get("type") == "attachment_ref"
    }
    for file_id in file_ids:
        stored = db.get(StoredFile, file_id)
        if stored is None:
            raise not_found("附件")
        allowed = (
            db.scalar(
                select(ProjectAttachment.id).where(
                    ProjectAttachment.project_id == section.project_id,
                    ProjectAttachment.file_id == file_id,
                )
            )
            is not None
            or db.scalar(
                select(AssetAttachment.id).where(AssetAttachment.file_id == file_id).limit(1)
            )
            is not None
        )
        if not allowed:
            document = db.scalar(select(TenderDocument).where(TenderDocument.file_id == file_id))
            if document:
                project_access(db, document.project_id, user)
                allowed = document.project_id == section.project_id
        if not allowed:
            raise not_found("附件")


@router.patch("/{section_id}")
def patch_section(section_id: str, payload: SectionPatch, db: DB, user: CurrentUser):
    section, project = section_context(db, section_id, user, "edit")
    if payload.project_version is not None:
        check_project_version(project, payload.project_version)
        check_section_version(section, payload.version)
    elif payload.version is not None and payload.version == section.version:
        check_section_version(section, payload.version)
    else:
        check_project_version(project, payload.version)
    values = payload.model_dump(exclude_unset=True, exclude={"version", "project_version"})
    if section.locked and values:
        raise bad_request("招标固定章节标题与格式策略不可修改", code="section_locked")
    for key, value in values.items():
        setattr(section, key, value)
    section.version += 1
    section.review_status = (
        "unconfirmed" if section.review_status != "needs_review" else section.review_status
    )
    touch_project(db, project)
    record_activity(db, user.id, "section.updated", "section", section.id, project.id, values)
    commit(db)
    return model_dict(section)


@router.post("/{section_id}:move")
def move(section_id: str, payload: SectionMove, db: DB, user: CurrentUser):
    section, project = section_context(db, section_id, user, "edit")
    if payload.project_version is not None:
        check_project_version(project, payload.project_version)
        check_section_version(section, payload.version)
    else:
        check_project_version(project, payload.version)
    move_section(db, section, payload.parent_id, payload.position)
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "section.moved",
        "section",
        section.id,
        project.id,
        {"parent_id": payload.parent_id, "position": payload.position},
    )
    commit(db)
    return model_dict(section)


@router.post("/{section_id}:select-version")
def select_version(section_id: str, payload: SelectVersion, db: DB, user: CurrentUser):
    section, project = section_context(db, section_id, user, "edit")
    if payload.project_version is not None:
        check_project_version(project, payload.project_version)
        check_section_version(section, payload.version)
    else:
        check_project_version(project, payload.version)
    candidate = find_section_candidate(db, section.id, payload.candidate_id)
    if candidate is None or candidate.section_id != section.id or candidate.status != "active":
        raise not_found("候选版本")
    revision = select_candidate(db, section, candidate, user.id)
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "section.version_selected",
        "section",
        section.id,
        project.id,
        {"candidate_id": candidate.id, "revision_id": revision.id},
    )
    impacted = db.scalars(
        select(ProjectSection)
        .join(
            SectionDependency,
            SectionDependency.section_id == ProjectSection.id,
        )
        .where(SectionDependency.depends_on_section_id == section.id)
    ).all()
    commit(db)
    serialized = revision_dict(revision)
    return {
        **serialized,
        "section": model_dict(section),
        "revision": serialized,
        "impacted_sections": [
            {"id": dependent.id, "title": dependent.title} for dependent in impacted
        ],
    }


@router.post("/{section_id}/revisions", status_code=201)
def save_revision(section_id: str, payload: SectionRevisionCreate, db: DB, user: CurrentUser):
    section, project = section_context(db, section_id, user, "edit")
    if payload.base_version is not None:
        check_section_version(section, payload.base_version)
        check_project_version(project, payload.project_version)
    else:
        check_project_version(project, payload.version)
    if section.content_mode == "group":
        raise bad_request("分组章节不能直接承载正文")
    validate_attachment_access(db, section, payload.content_json, user)
    validate_tender_references(db, section, payload.content_json)
    revision = create_revision(
        db, section, payload.content_json, "manual", user.id, make_manual_candidate=True
    )
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "section.revision_created",
        "section_revision",
        revision.id,
        project.id,
        {"section_id": section.id, "revision_no": revision.revision_no},
    )
    commit(db)
    return revision_dict(revision)


@router.post("/{section_id}:confirm")
def confirm(section_id: str, payload: ConfirmSection, db: DB, user: CurrentUser):
    section, project = section_context(db, section_id, user, "review")
    if payload.selected_revision_id is not None:
        check_section_version(section, payload.version)
        check_project_version(project, payload.project_version)
        if payload.selected_revision_id != section.selected_revision_id:
            raise conflict("当前章节修订已变化，请刷新后确认")
    else:
        check_project_version(project, payload.version)
    if section.content_mode == "group" or not section.selected_revision_id:
        raise bad_request("分组或空章节不能单独确认", code="invalid_section_state")
    open_gap = db.scalar(
        select(Gap.id)
        .where(Gap.section_id == section.id, Gap.status == "open", Gap.blocking.is_(True))
        .limit(1)
    )
    revision = db.get(ProjectSectionRevision, section.selected_revision_id)
    if open_gap or section.content_status != "ready" or placeholders(revision.content_json):
        raise bad_request("请先补齐内容并关闭阻塞缺口", code="section_not_ready")
    section.review_status = "confirmed"
    section.version += 1
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "section.confirmed",
        "section",
        section.id,
        project.id,
        {"revision_id": revision.id},
    )
    commit(db)
    return model_dict(section)
