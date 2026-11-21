from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, utcnow
from app.models.base import CreatedAt, UUIDPrimaryKey


class User(UUIDPrimaryKey, CreatedAt, Base):
    __tablename__ = "users"

    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    display_name: Mapped[str] = mapped_column(String(120))
    global_role: Mapped[str] = mapped_column(String(30), default="viewer", index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class SessionToken(UUIDPrimaryKey, Base):
    __tablename__ = "sessions"

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
