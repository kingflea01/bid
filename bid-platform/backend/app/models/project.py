from datetime import date, datetime
from typing import Any

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class Project(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "projects"
    name: Mapped[str] = mapped_column(String(240))
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(200), index=True)
    procurement_type: Mapped[str] = mapped_column(String(60))
    package: Mapped[str | None] = mapped_column(String(60), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    project_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    source_project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    parse_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class ProjectMember(CreatedAt, Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id"),)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    project_role: Mapped[str] = mapped_column(String(30))


class ProjectConfigRef(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_config_refs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), unique=True, index=True)
    company_revision_id: Mapped[str] = mapped_column(ForeignKey("company_revisions.id"))
    product_revision_id: Mapped[str] = mapped_column(ForeignKey("product_revisions.id"))
    template_revision_id: Mapped[str] = mapped_column(ForeignKey("template_revisions.id"))
    redline_rule_ids_json: Mapped[list[str]] = mapped_column(JSONVariant, default=list)


class ProjectAttachment(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "project_attachments"
    __table_args__ = (UniqueConstraint("project_id", "file_id"),)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    file_id: Mapped[str] = mapped_column(ForeignKey("files.id"), index=True)
    attachment_type: Mapped[str] = mapped_column(String(80), default="supporting")
    uploaded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class Job(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "jobs"
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    rq_job_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Activity(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "activities"
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str] = mapped_column(String(36))
    detail_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
