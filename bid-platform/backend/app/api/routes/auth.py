from fastapi import APIRouter, Request, Response
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import (
    DUMMY_HASH,
    create_session,
    delete_session,
    login_rate_limiter,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import LoginRequest, UserOut
from app.services.persistence import commit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response, db: DB):
    client = request.client.host if request.client else "unknown"
    rate_key = f"{client}:{payload.username.lower()}"
    if not login_rate_limiter.allowed(rate_key):
        raise AppError(429, "login_rate_limited", "登录尝试过多，请稍后重试")
    user = db.scalar(select(User).where(User.username == payload.username))
    valid = verify_password(user.password_hash if user else DUMMY_HASH, payload.password)
    if not user or not user.active or not valid:
        login_rate_limiter.failure(rate_key)
        raise AppError(401, "invalid_credentials", "用户名或密码错误")
    login_rate_limiter.success(rate_key)
    raw_token, _ = create_session(db, user)
    commit(db)
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        raw_token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.session_secure,
        samesite="lax",
        path="/",
    )
    return user


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    settings = get_settings()
    delete_session(db, request.cookies.get(settings.session_cookie_name))
    commit(db)
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
