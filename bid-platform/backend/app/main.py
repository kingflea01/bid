import logging
import re
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select

from alembic import command
from app.api.routes import (
    analysis,
    assets,
    auth,
    candidates,
    companies,
    exports,
    facts,
    gaps,
    products,
    projects,
    redlines,
    risks,
    sections,
    snapshots,
    tasks,
    templates,
    users,
)
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.errors import AppError
from app.core.security import hash_password
from app.models.user import User

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]


def migrate_database() -> None:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "alembic"))
    command.upgrade(config, "head")


def bootstrap_admin() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(User.id).limit(1)) is None:
            db.add(
                User(
                    username=settings.admin_username,
                    display_name="系统管理员",
                    global_role="admin",
                    password_hash=hash_password(settings.admin_password),
                )
            )
            db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    migrate_database()
    bootstrap_admin()
    yield


app = FastAPI(title=get_settings().app_name, version="0.1.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID", "Last-Event-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    supplied = request.headers.get("X-Request-ID", "")
    request.state.request_id = (
        supplied if re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", supplied) else str(uuid4())
    )
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


def error_response(request: Request, status: int, code: str, message: str, details=None):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status,
        content={"code": code, "message": message, "details": details, "request_id": request_id},
    )


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return error_response(request, exc.status_code, exc.code, exc.message, exc.details)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    details = [
        {"loc": list(error["loc"]), "message": error["msg"], "type": error["type"]}
        for error in exc.errors()
    ]
    return error_response(request, 422, "validation_error", "请求参数校验失败", details)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    return error_response(request, exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(Exception)
async def internal_error_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled %s at request %s",
        type(exc).__name__,
        getattr(request.state, "request_id", "unknown"),
    )
    return error_response(request, 500, "internal_error", "服务器处理请求失败")


for router in (
    auth.router,
    users.router,
    companies.router,
    products.router,
    redlines.router,
    assets.router,
    templates.router,
    projects.router,
    analysis.router,
    tasks.router,
    sections.router,
    candidates.router,
    gaps.router,
    risks.router,
    facts.router,
    snapshots.router,
    exports.router,
):
    app.include_router(router, prefix="/api/v1")


@app.get("/healthz")
def healthcheck():
    return {"status": "ok"}
