from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.core.security import get_session_user
from app.models.user import User

DB = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: DB) -> User:
    token = request.cookies.get(get_settings().session_cookie_name)
    user = get_session_user(db, token)
    if user is None:
        raise AppError(401, "unauthenticated", "请先登录")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def session_cookie_name() -> str:
    return get_settings().session_cookie_name
