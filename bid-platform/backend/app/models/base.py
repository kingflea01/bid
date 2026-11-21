from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import new_uuid, utcnow

JSONVariant = JSON().with_variant(JSONB, "postgresql")


class UUIDPrimaryKey:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)


class CreatedAt:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )


class JSONRecord:
    content_json: Mapped[dict[str, Any]] = mapped_column(JSONVariant, default=dict, nullable=False)
