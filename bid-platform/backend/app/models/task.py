from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class AIRun(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "ai_runs"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True, index=True)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    input_hash: Mapped[str] = mapped_column(String(64), index=True)
    prompt_version: Mapped[str] = mapped_column(String(40))
    model: Mapped[str] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    input_manifest_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    output_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    token_usage: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ExportTask(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "export_tasks"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("project_snapshots.id"))
    job_id: Mapped[str | None] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    export_kind: Mapped[str] = mapped_column(String(20))
    format: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(30), default="queued", index=True)
    qa_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict)
    file_id: Mapped[str | None] = mapped_column(ForeignKey("files.id"), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
