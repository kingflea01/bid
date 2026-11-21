from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[A-Za-z0-9_.@-]{3,80}$")
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=1, max_length=120)
    global_role: str = Field(pattern=r"^(admin|config_admin|editor|reviewer|viewer)$")
    active: bool = True


class UserPatch(BaseModel):
    password: str | None = Field(default=None, min_length=12, max_length=256)
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    global_role: str | None = Field(
        default=None, pattern=r"^(admin|config_admin|editor|reviewer|viewer)$"
    )
    active: bool | None = None


class UserOut(ORMModel):
    id: str
    username: str
    display_name: str
    global_role: str
    active: bool
