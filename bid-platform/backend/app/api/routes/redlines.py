from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.core.errors import bad_request, not_found
from app.core.permissions import require_global
from app.models.config import Company, Product, RedlineRule
from app.schemas.config import RedlineCreate, RedlinePatch
from app.services.config_publishing import publish_redline
from app.services.persistence import commit, model_dict, models_dict

router = APIRouter(prefix="/redline-rules", tags=["redlines"])


@router.post("", status_code=201)
def create_redline(payload: RedlineCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    parent_model = Company if payload.scope_type == "company" else Product
    if db.get(parent_model, payload.scope_id) is None:
        raise not_found("红线所属配置")
    values = payload.model_dump()
    requested_status = values.pop("status")
    record = RedlineRule(**values)
    db.add(record)
    db.flush()
    record.lineage_id = record.id
    if requested_status == "published":
        publish_redline(db, record, user.id)
    commit(db)
    return model_dict(record)


@router.get("")
def list_redlines(
    db: DB,
    user: CurrentUser,
    scope_type: str | None = Query(default=None),
    scope_id: str | None = Query(default=None),
    include_archived: bool = False,
):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    statement = select(RedlineRule)
    if scope_type:
        statement = statement.where(RedlineRule.scope_type == scope_type)
    if scope_id:
        statement = statement.where(RedlineRule.scope_id == scope_id)
    if not include_archived:
        statement = statement.where(RedlineRule.status != "archived")
    records = db.scalars(statement.order_by(RedlineRule.category, RedlineRule.revision_no)).all()
    return models_dict(records)


@router.patch("/{rule_id}")
def patch_redline(rule_id: str, payload: RedlinePatch, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(RedlineRule, rule_id)
    if record is None:
        raise not_found("红线")
    values = payload.model_dump(exclude_unset=True)
    if record.status == "archived":
        raise bad_request("已归档红线不可修改", code="invalid_revision_state")
    requested_status = values.pop("status", None)
    if record.status == "published":
        if requested_status == "archived" and not values:
            record.status = "archived"
            result = record
        elif requested_status == "published" and not values:
            result = record
        elif requested_status is not None:
            raise bad_request("发布版本不能与其他字段同时修改")
        else:
            current = db.scalar(
                select(func.max(RedlineRule.revision_no)).where(
                    RedlineRule.lineage_id == record.lineage_id
                )
            )
            data = {
                "lineage_id": record.lineage_id,
                "scope_type": record.scope_type,
                "scope_id": record.scope_id,
                "category": record.category,
                "position": record.position,
                "condition_json": record.condition_json,
                "action": record.action,
                "legal_review": record.legal_review,
                "revision_no": (current or record.revision_no) + 1,
                "status": "draft",
            }
            data.update(values)
            result = RedlineRule(**data)
            db.add(result)
    else:
        for key, value in values.items():
            setattr(record, key, value)
        if requested_status == "archived":
            record.status = "archived"
        elif requested_status == "published":
            publish_redline(db, record, user.id)
        result = record
    commit(db)
    return model_dict(result)


@router.post("/{rule_id}:publish")
def publish(rule_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(RedlineRule, rule_id)
    if record is None:
        raise not_found("红线")
    publish_redline(db, record, user.id)
    commit(db)
    return model_dict(record)
