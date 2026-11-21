from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.errors import not_found
from app.core.permissions import require_global
from app.models.config import Product, ProductRevision
from app.schemas.config import ProductCreate, ProductPatch, ProductRevisionCreate
from app.services.config_publishing import next_revision, publish_revision
from app.services.persistence import commit, model_dict

router = APIRouter(tags=["products"])


@router.post("/products", status_code=201)
def create_product(payload: ProductCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = Product(**payload.model_dump())
    db.add(record)
    commit(db)
    return model_dict(record)


@router.get("/products")
def list_products(db: DB, user: CurrentUser):
    require_global(user, "config_admin", "editor", "reviewer", "viewer")
    records = db.scalars(select(Product).order_by(Product.code)).all()
    revisions = (
        db.scalars(
            select(ProductRevision)
            .where(ProductRevision.product_id.in_([record.id for record in records]))
            .order_by(ProductRevision.revision_no.desc())
        ).all()
        if records
        else []
    )
    grouped = {}
    for revision in revisions:
        grouped.setdefault(revision.product_id, []).append(model_dict(revision))
    return [{**model_dict(record), "revisions": grouped.get(record.id, [])} for record in records]


@router.patch("/products/{product_id}")
def patch_product(product_id: str, payload: ProductPatch, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(Product, product_id)
    if record is None:
        raise not_found("产品")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") == "active":
        values.pop("status")
        if record.status == "archived":
            record.status = "draft"
    for key, value in values.items():
        setattr(record, key, value)
    commit(db)
    return model_dict(record)


@router.post("/products/{product_id}/revisions", status_code=201)
def create_revision(product_id: str, payload: ProductRevisionCreate, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    if db.get(Product, product_id) is None:
        raise not_found("产品")
    record = ProductRevision(
        product_id=product_id,
        revision_no=next_revision(db, ProductRevision, ProductRevision.product_id, product_id),
        **payload.model_dump(),
    )
    db.add(record)
    commit(db)
    return model_dict(record)


@router.post("/product-revisions/{revision_id}:publish")
def publish(revision_id: str, db: DB, user: CurrentUser):
    require_global(user, "config_admin")
    record = db.get(ProductRevision, revision_id)
    if record is None:
        raise not_found("产品修订")
    publish_revision(db, record, user.id)
    commit(db)
    return model_dict(record)
