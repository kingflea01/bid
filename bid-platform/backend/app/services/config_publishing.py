from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import bad_request
from app.models.config import (
    Company,
    CompanyRevision,
    Product,
    ProductRevision,
    RedlineRule,
    Template,
    TemplateRevision,
)


def next_revision(db: Session, model, field, identity: str) -> int:
    current = db.scalar(select(func.max(model.revision_no)).where(field == identity))
    return (current or 0) + 1


def publish_revision(db: Session, revision, user_id: str) -> None:
    if revision.status != "draft":
        raise bad_request("只有草稿修订可以发布", code="invalid_revision_state")
    if isinstance(revision, CompanyRevision):
        identity_field = CompanyRevision.company_id
        identity = revision.company_id
        parent = db.get(Company, identity)
    elif isinstance(revision, ProductRevision):
        identity_field = ProductRevision.product_id
        identity = revision.product_id
        parent = db.get(Product, identity)
    elif isinstance(revision, TemplateRevision):
        identity_field = TemplateRevision.template_id
        identity = revision.template_id
        parent = db.get(Template, identity)
    else:
        raise TypeError("unsupported revision")
    if parent is None or parent.status == "archived":
        raise bad_request("配置身份已归档", code="invalid_revision_state")
    siblings = db.scalars(
        select(type(revision)).where(
            identity_field == identity, type(revision).status == "published"
        )
    ).all()
    for sibling in siblings:
        sibling.status = "archived"
    revision.status = "published"
    revision.published_by = user_id
    revision.published_at = utcnow()
    parent.status = "published"
    db.flush()


def publish_redline(db: Session, rule: RedlineRule, user_id: str) -> None:
    if rule.status != "draft":
        raise bad_request("只有红线草稿可以发布", code="invalid_revision_state")
    siblings = db.scalars(
        select(RedlineRule).where(
            RedlineRule.lineage_id == rule.lineage_id, RedlineRule.status == "published"
        )
    ).all()
    for sibling in siblings:
        sibling.status = "archived"
    rule.status = "published"
    rule.published_by = user_id
    db.flush()
