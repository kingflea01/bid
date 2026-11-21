from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.errors import not_found
from app.core.permissions import require_global
from app.models.config import Company, CompanyRevision
from app.schemas.config import CompanyCreate, CompanyPatch, CompanyRevisionCreate
from app.services.config_publishing import next_revision, publish_revision
from app.services.persistence import commit, model_dict

router = APIRouter(tags=["companies"])


@router.post("/companies", status_code=201)
def create_company(payload: CompanyCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = Company(**payload.model_dump())
    db.add(record)
    commit(db)
    return model_dict(record)


@router.get("/companies")
def list_companies(db: DB, user: CurrentUser):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    records = db.scalars(select(Company).order_by(Company.code)).all()
    revisions = (
        db.scalars(
            select(CompanyRevision)
            .where(CompanyRevision.company_id.in_([record.id for record in records]))
            .order_by(CompanyRevision.revision_no.desc())
        ).all()
        if records
        else []
    )
    grouped = {}
    for revision in revisions:
        grouped.setdefault(revision.company_id, []).append(model_dict(revision))
    return [{**model_dict(record), "revisions": grouped.get(record.id, [])} for record in records]


@router.patch("/companies/{company_id}")
def patch_company(company_id: str, payload: CompanyPatch, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(Company, company_id)
    if record is None:
        raise not_found("企业")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "active":
        values.pop("status")
        if record.status == "archived":
            record.status = "draft"
    for key, value in values.items():
        setattr(record, key, value)
    commit(db)
    return model_dict(record)


@router.post("/companies/{company_id}/revisions", status_code=201)
def create_revision(company_id: str, payload: CompanyRevisionCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if db.get(Company, company_id) is None:
        raise not_found("企业")
    record = CompanyRevision(
        company_id=company_id,
        revision_no=next_revision(db, CompanyRevision, CompanyRevision.company_id, company_id),
        fields_json=payload.fields_json,
    )
    db.add(record)
    commit(db)
    return model_dict(record)


@router.post("/company-revisions/{revision_id}:publish")
def publish(revision_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(CompanyRevision, revision_id)
    if record is None:
        raise not_found("企业修订")
    publish_revision(db, record, user.id)
    commit(db)
    return model_dict(record)
