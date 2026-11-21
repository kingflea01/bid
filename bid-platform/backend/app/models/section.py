from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class ProjectSection(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_sections"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    parent_id: Mapped[str | None] = mapped_column(ForeignKey("project_sections.id"), nullable=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    section_key: Mapped[str] = mapped_column(String(300), index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    locked: Mapped[bool] = mapped_column(default=False)
    content_mode: Mapped[str] = mapped_column(String(40), default="placeholder")
    selected_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    content_status: Mapped[str] = mapped_column(String(30), default="empty")
    review_status: Mapped[str] = mapped_column(String(30), default="unconfirmed")
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_anchor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    source_end_anchor: Mapped[str | None] = mapped_column(String(160), nullable=True)
    mapping_status: Mapped[str] = mapped_column(String(30), default="resolved")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectSectionRevision(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_section_revisions"
    __table_args__ = (UniqueConstraint("section_id", "revision_no"),)
    section_id: Mapped[str] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"), index=True
    )
    revision_no: Mapped[int] = mapped_column(Integer)
    content_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    source_type: Mapped[str] = mapped_column(String(40))
    source_asset_revision_id: Mapped[str | None] = mapped_column(
        ForeignKey("asset_revisions.id"), nullable=True
    )
    source_history_revision_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SectionCandidate(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "section_candidates"
    section_id: Mapped[str] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"), index=True
    )
    candidate_type: Mapped[str] = mapped_column(String(30))
    candidate_id: Mapped[str] = mapped_column(String(36), index=True)
    rank_score: Mapped[float] = mapped_column(Float)
    rank_reasons_json: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    status: Mapped[str] = mapped_column(String(30), default="active")


class SectionRequirement(Base):
    __tablename__ = "section_requirements"
    section_id: Mapped[str] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"), primary_key=True
    )
    requirement_id: Mapped[str] = mapped_column(
        ForeignKey("requirements.id", ondelete="CASCADE"), primary_key=True
    )
    mapping_source: Mapped[str] = mapped_column(String(30), default="deterministic")
    mapping_status: Mapped[str] = mapped_column(String(30), default="suggested")
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)


class SectionDependency(Base):
    __tablename__ = "section_dependencies"
    section_id: Mapped[str] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"), primary_key=True
    )
    depends_on_section_id: Mapped[str] = mapped_column(
        ForeignKey("project_sections.id", ondelete="CASCADE"), primary_key=True
    )
    dependency_type: Mapped[str] = mapped_column(String(30), primary_key=True)
    fact_keys_json: Mapped[list[str]] = mapped_column(JSONVariant, default=list)


class ProjectFact(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_facts"
    __table_args__ = (UniqueConstraint("project_id", "fact_key"),)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    fact_key: Mapped[str] = mapped_column(String(160), index=True)
    value_json: Mapped[Any] = mapped_column(JSONVariant)
    value_type: Mapped[str] = mapped_column(String(30))
    source_type: Mapped[str] = mapped_column(String(30), default="manual")
    source_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="unconfirmed")
    confirmed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Gap(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "gaps"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    section_id: Mapped[str | None] = mapped_column(ForeignKey("project_sections.id"), nullable=True)
    requirement_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    gap_type: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(500))
    blocking: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(30), default="open", index=True)
    resolved_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)


class ProjectSnapshot(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "snapshot_no"),)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_no: Mapped[int] = mapped_column(Integer)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tree_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    selected_revisions_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    facts_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    risk_states_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    gaps_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    config_refs_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    document_states_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    state_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
