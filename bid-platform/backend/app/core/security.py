import hashlib
import secrets
import threading
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.models.user import SessionToken, User

_password_hasher = PasswordHasher()
DUMMY_HASH = _password_hasher.hash("not-a-real-user-password")


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _password_hasher.verify(password_hash, password)
    except (VerifyMismatchError, ValueError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(db: Session, user: User) -> tuple[str, SessionToken]:
    raw_token = secrets.token_urlsafe(40)
    session = SessionToken(
        token_hash=hash_token(raw_token),
        user_id=user.id,
        expires_at=utcnow() + timedelta(hours=get_settings().session_ttl_hours),
    )
    db.add(session)
    db.flush()
    return raw_token, session


def get_session_user(db: Session, raw_token: str | None) -> User | None:
    if not raw_token:
        return None
    session = db.scalar(
        select(SessionToken).where(SessionToken.token_hash == hash_token(raw_token))
    )
    if session is None:
        return None
    expires_at = session.expires_at
    now = utcnow()
    if expires_at.tzinfo is None:
        now = now.replace(tzinfo=None)
    if expires_at <= now:
        db.delete(session)
        db.commit()
        return None
    user = db.get(User, session.user_id)
    return user if user and user.active else None


def delete_session(db: Session, raw_token: str | None) -> None:
    if raw_token:
        db.execute(delete(SessionToken).where(SessionToken.token_hash == hash_token(raw_token)))


class LoginRateLimiter:
    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            recent = [v for v in self._attempts.get(key, []) if now - v < self.window_seconds]
            self._attempts[key] = recent
            return len(recent) < self.max_attempts

    def failure(self, key: str) -> None:
        with self._lock:
            self._attempts.setdefault(key, []).append(time.monotonic())

    def success(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter()
