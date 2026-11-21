from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class StoredFile(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "files"
    sha256: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    path: Mapped[str] = mapped_column(String(500))
    mime_type: Mapped[str] = mapped_column(String(150))
    size: Mapped[int] = mapped_column(Integer)
    original_name: Mapped[str] = mapped_column(String(500))
    uploaded_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class TenderDocument(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "tender_documents"
    __table_args__ = (UniqueConstraint("project_id", "sha256"),)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"))
    document_type: Mapped[str] = mapped_column(String(20), default="tender")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(30), default="uploaded", index=True)
    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parser_version: Mapped[str] = mapped_column(String(40), default="v1")
    parse_qa_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    scanned_pages_json: Mapped[list[int]] = mapped_column(JSONVariant, default=list)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    parsed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TenderBlock(UUIDPrimaryKey, Base):
    __tablename__ = "tender_blocks"
    __table_args__ = (UniqueConstraint("document_id", "anchor_key"),)
    document_id: Mapped[str] = mapped_column(
        ForeignKey("tender_documents.id", ondelete="CASCADE"), index=True
    )
    anchor_key: Mapped[str] = mapped_column(String(160), index=True)
    block_type: Mapped[str] = mapped_column(String(30))
    order_no: Mapped[int] = mapped_column(Integer)
    page_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    paragraph_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    table_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bbox_json: Mapped[list[float] | None] = mapped_column(JSONVariant, nullable=True)
    text: Mapped[str] = mapped_column(Text)
    ooxml_path: Mapped[str | None] = mapped_column(String(300), nullable=True)
    style_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)


class TenderOutline(UUIDPrimaryKey, Base):
    __tablename__ = "tender_outlines"
    document_id: Mapped[str] = mapped_column(
        ForeignKey("tender_documents.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("tender_outlines.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    level: Mapped[int] = mapped_column(Integer)
    source_start_anchor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_end_anchor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    recognition_confidence: Mapped[float] = mapped_column(Float, default=1.0)


class Requirement(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "requirements"
    document_id: Mapped[str] = mapped_column(ForeignKey("tender_documents.id"), index=True)
    code: Mapped[str] = mapped_column(String(80), index=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    response_type: Mapped[str] = mapped_column(String(50))
    text: Mapped[str] = mapped_column(Text)
    normalized_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    mandatory_level: Mapped[str] = mapped_column(String(30), default="normal")
    score_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="needs_review", index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class RequirementAnchor(Base):
    __tablename__ = "requirement_anchors"
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True
    )
    anchor_key: Mapped[str] = mapped_column(String(160), primary_key=True)
    quote: Mapped[str] = mapped_column(Text)
