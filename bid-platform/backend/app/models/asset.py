from datetime import date, datetime
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class Asset(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "assets"
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(240))
    asset_type: Mapped[str] = mapped_column(String(60), index=True)
    scope: Mapped[str] = mapped_column(String(30), default="company", index=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    project_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    section_key: Mapped[str | None] = mapped_column(String(240), nullable=True, index=True)
    classification: Mapped[str] = mapped_column(String(30), default="internal")
    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)


class AssetVariant(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "asset_variants"
    __table_args__ = (UniqueConstraint("asset_id", "code"),)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")


class AssetRevision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "asset_revisions"
    __table_args__ = (UniqueConstraint("variant_id", "revision_no"),)
    variant_id: Mapped[str] = mapped_column(ForeignKey("asset_variants.id"), index=True)
    revision_no: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    source_format: Mapped[str] = mapped_column(String(30), default="blocks")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    published_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AssetAttachment(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "asset_attachments"
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"), index=True)
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"))
    attachment_type: Mapped[str] = mapped_column(String(80))
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
