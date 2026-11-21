from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, new_uuid, utcnow
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class Company(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "companies"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")


class CompanyRevision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "company_revisions"
    __table_args__ = (UniqueConstraint("company_id", "revision_no"),)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Product(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "products"
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="draft")


class ProductRevision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "product_revisions"
    __table_args__ = (UniqueConstraint("product_id", "revision_no"),)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    fields_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    technical_fields_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RedlineRule(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "redline_rules"
    lineage_id: Mapped[str] = mapped_column(String(36), default=new_uuid, index=True)
    scope_type: Mapped[str] = mapped_column(String(20), index=True)
    scope_id: Mapped[str] = mapped_column(String(36), index=True)
    category: Mapped[str] = mapped_column(String(100))
    position: Mapped[str] = mapped_column(String(500))
    condition_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    action: Mapped[str] = mapped_column(String(30))
    legal_review: Mapped[bool] = mapped_column(default=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Template(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "templates"
    name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")


class TemplateRevision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "template_revisions"
    __table_args__ = (UniqueConstraint("template_id", "revision_no"),)
    template_id: Mapped[str] = mapped_column(ForeignKey("templates.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    nodes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    rules_version: Mapped[str] = mapped_column(String(40), default="v1")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
