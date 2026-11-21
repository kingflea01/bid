from datetime import date

from fastapi import APIRouter, File, Form, UploadFile
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.database import utcnow
from app.core.errors import bad_request, not_found
from app.core.permissions import require_global
from app.models.asset import Asset, AssetAttachment, AssetRevision, AssetVariant
from app.schemas.asset import AssetCreate, AssetRevisionCreate, AssetVariantCreate
from app.services.files.store import FileStore, validate_signature
from app.services.persistence import commit, model_dict, models_dict
from app.services.workspace.content import normalize_block_aliases

router = APIRouter(tags=["assets"])


@router.post("/assets", status_code=201)
def create_asset(payload: AssetCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if payload.valid_from and payload.valid_to and payload.valid_from > payload.valid_to:
        raise bad_request("素材有效期起止顺序错误")
    values = payload.model_dump()
    if values.get("status") == "active":
        values["status"] = "draft"
    values["owner_id"] = values["owner_id"] or user.id
    record = Asset(**values)
    db.add(record)
    commit(db)
    return model_dict(record)


@router.get("/assets")
def list_assets(
    db: DB,
    user: CurrentUser,
    product_id: str | None = None,
    customer_name: str | None = None,
    asset_type: str | None = None,
):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    statement = select(Asset)
    if product_id:
        statement = statement.where(Asset.product_id == product_id)
    if customer_name:
        statement = statement.where(Asset.customer_name == customer_name)
    if asset_type:
        statement = statement.where(Asset.asset_type == asset_type)
    records = db.scalars(statement.order_by(Asset.code)).all()
    variants = (
        db.scalars(
            select(AssetVariant)
            .where(AssetVariant.asset_id.in_([record.id for record in records]))
            .order_by(AssetVariant.code)
        ).all()
        if records
        else []
    )
    revisions = (
        db.scalars(
            select(AssetRevision)
            .where(AssetRevision.variant_id.in_([variant.id for variant in variants]))
            .order_by(AssetRevision.revision_no.desc())
        ).all()
        if variants
        else []
    )
    revision_groups = {}
    for revision in revisions:
        revision_groups.setdefault(revision.variant_id, []).append(model_dict(revision))
    variant_groups = {}
    for variant in variants:
        variant_groups.setdefault(variant.asset_id, []).append(
            {
                **model_dict(variant),
                "revisions": revision_groups.get(variant.id, []),
            }
        )
    return [
        {**model_dict(record), "variants": variant_groups.get(record.id, [])} for record in records
    ]


@router.post("/assets/{asset_id}/variants", status_code=201)
def create_variant(asset_id: str, payload: AssetVariantCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if db.get(Asset, asset_id) is None:
        raise not_found("素材")
    record = AssetVariant(asset_id=asset_id, **payload.model_dump())
    db.add(record)
    commit(db)
    return model_dict(record)


@router.post("/variants/{variant_id}/revisions", status_code=201)
def create_revision(variant_id: str, payload: AssetRevisionCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    variant = db.get(AssetVariant, variant_id)
    if variant is None:
        raise not_found("素材方案")
    from app.services.config_publishing import next_revision

    values = payload.model_dump()
    values["content_json"] = normalize_block_aliases(values["content_json"])
    record = AssetRevision(
        variant_id=variant_id,
        revision_no=next_revision(db, AssetRevision, AssetRevision.variant_id, variant_id),
        created_by=user.id,
        **values,
    )
    db.add(record)
    commit(db)
    return model_dict(record)


@router.get("/variants/{variant_id}/revisions")
def list_revisions(variant_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if db.get(AssetVariant, variant_id) is None:
        raise not_found("素材方案")
    records = db.scalars(
        select(AssetRevision)
        .where(AssetRevision.variant_id == variant_id)
        .order_by(AssetRevision.revision_no.desc())
    ).all()
    return models_dict(records)


@router.post("/asset-revisions/{revision_id}:publish")
def publish(revision_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(AssetRevision, revision_id)
    if record is None:
        raise not_found("素材修订")
    if record.status != "draft":
        raise bad_request("只有素材草稿可以发布", code="invalid_revision_state")
    variant = db.get(AssetVariant, record.variant_id)
    asset = db.get(Asset, variant.asset_id) if variant else None
    if asset is None or asset.status == "archived":
        raise bad_request("素材已归档", code="invalid_revision_state")
    siblings = db.scalars(
        select(AssetRevision).where(
            AssetRevision.variant_id == record.variant_id, AssetRevision.status == "published"
        )
    ).all()
    for sibling in siblings:
        sibling.status = "archived"
    record.status = "published"
    record.published_by = user.id
    record.published_at = utcnow()
    variant.status = "published"
    asset.status = "published"
    commit(db)
    return model_dict(record)


@router.post("/assets/{asset_id}/attachments", status_code=201)
async def attach_file(
    asset_id: str,
    db: DB,
    user: CurrentUser,
    file: UploadFile = File(...),
    attachment_type: str = Form(...),
    valid_to: date | None = Form(None),
):
    require_global(user, "config_admin")
    if db.get(Asset, asset_id) is None:
        raise not_found("素材")
    data = await file.read(50 * 1024 * 1024 + 1)
    mime = validate_signature(file.filename or "", file.content_type or "", data)
    stored = FileStore().save(db, data, file.filename or "attachment", mime, user.id)
    record = AssetAttachment(
        asset_id=asset_id,
        file_id=stored.id,
        attachment_type=attachment_type,
        valid_to=valid_to,
    )
    db.add(record)
    commit(db)
    return model_dict(record)
