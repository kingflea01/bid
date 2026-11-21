from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.core.errors import bad_request, not_found
from app.core.permissions import require_global
from app.core.security import hash_password
from app.models.user import User
from app.schemas.auth import UserCreate, UserOut, UserPatch
from app.services.persistence import commit

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserOut])
def list_users(db: DB, user: CurrentUser):
    require_global(user, "admin")
    return db.scalars(select(User).order_by(User.username)).all()


@router.post("", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, db: DB, user: CurrentUser):
    require_global(user, "admin")
    record = User(
        **payload.model_dump(exclude={"password"}), password_hash=hash_password(payload.password)
    )
    db.add(record)
    commit(db)
    return record


@router.patch("/{user_id}", response_model=UserOut)
def patch_user(user_id: str, payload: UserPatch, db: DB, actor: CurrentUser):
    require_global(actor, "admin")
    record = db.get(User, user_id)
    if record is None:
        raise not_found("用户")
    values = payload.model_dump(exclude_unset=True, exclude={"password"})
    if record.id == actor.id and values.get("active") is False:
        raise bad_request("不能停用当前登录管理员")
    for key, value in values.items():
        setattr(record, key, value)
    if payload.password:
        record.password_hash = hash_password(payload.password)
    commit(db)
    return record
