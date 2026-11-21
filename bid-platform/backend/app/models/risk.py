from typing import Any

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import CreatedAt, JSONVariant, UUIDPrimaryKey


class Risk(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "risks"
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    requirement_id: Mapped[str | None] = mapped_column(ForeignKey("requirements.id"), nullable=True)
    redline_rule_id: Mapped[str | None] = mapped_column(
        ForeignKey("redline_rules.id"), nullable=True
    )
    category: Mapped[str] = mapped_column(String(100))
    conflict_type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(30), index=True)
    recommendation: Mapped[str] = mapped_column(Text)
    anchors_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    legal_review: Mapped[bool] = mapped_column(default=False)
    disposition: Mapped[str] = mapped_column(String(30), default="pending", index=True)
    disposed_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    disposition_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScoreAssessment(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "score_assessments"
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), index=True)
    requirement_id: Mapped[str] = mapped_column(ForeignKey("requirements.id"), index=True)
    score_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSONVariant, default=list)
    gap_json: Mapped[list[str]] = mapped_column(JSONVariant, default=list)
    status: Mapped[str] = mapped_column(String(30), default="estimated")
