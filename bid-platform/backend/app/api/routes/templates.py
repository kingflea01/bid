from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.errors import not_found
from app.core.permissions import require_global
from app.models.config import Template, TemplateRevision
from app.schemas.config import TemplateCreate, TemplatePatch, TemplateRevisionCreate
from app.services.config_publishing import next_revision, publish_revision
from app.services.persistence import commit, model_dict, models_dict

router = APIRouter(tags=["templates"])


@router.post("/templates", status_code=201)
def create_template(payload: TemplateCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = Template(name=payload.name, project_type=payload.project_type)
    db.add(record)
    db.flush()
    if payload.nodes_json:
        db.add(
            TemplateRevision(
                template_id=record.id,
                revision_no=1,
                nodes_json=payload.nodes_json,
            )
        )
    commit(db)
    return model_dict(record)


@router.get("/templates")
def list_templates(db: DB, user: CurrentUser):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    records = db.scalars(select(Template).order_by(Template.name)).all()
    revisions = (
        db.scalars(
            select(TemplateRevision)
            .where(TemplateRevision.template_id.in_([record.id for record in records]))
            .order_by(TemplateRevision.revision_no.desc())
        ).all()
        if records
        else []
    )
    grouped = {}
    for revision in revisions:
        grouped.setdefault(revision.template_id, []).append(model_dict(revision))
    return [{**model_dict(record), "revisions": grouped.get(record.id, [])} for record in records]


@router.patch("/templates/{template_id}")
def patch_template(template_id: str, payload: TemplatePatch, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(Template, template_id)
    if record is None:
        raise not_found("模板")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "active":
        values.pop("status")
        if record.status == "archived":
            record.status = "draft"
    for key, value in values.items():
        setattr(record, key, value)
    commit(db)
    return model_dict(record)


@router.post("/templates/{template_id}/revisions", status_code=201)
def create_revision(template_id: str, payload: TemplateRevisionCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if db.get(Template, template_id) is None:
        raise not_found("模板")
    record = TemplateRevision(
        template_id=template_id,
        revision_no=next_revision(db, TemplateRevision, TemplateRevision.template_id, template_id),
        **payload.model_dump(),
    )
    db.add(record)
    commit(db)
    return model_dict(record)


@router.get("/templates/{template_id}/revisions")
def list_revisions(template_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    if db.get(Template, template_id) is None:
        raise not_found("模板")
    records = db.scalars(
        select(TemplateRevision)
        .where(TemplateRevision.template_id == template_id)
        .order_by(TemplateRevision.revision_no.desc())
    ).all()
    return models_dict(records)


@router.post("/template-revisions/{revision_id}:publish")
def publish(revision_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(TemplateRevision, revision_id)
    if record is None:
        raise not_found("模板修订")
    publish_revision(db, record, user.id)
    commit(db)
    return model_dict(record)
