from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import forbidden, not_found
from app.models.project import Project, ProjectMember
from app.models.user import User

GLOBAL_ROLES = {"admin", "config_admin", "editor", "reviewer", "viewer"}
PROJECT_ROLES = {"editor", "reviewer", "viewer"}


def require_global(user: User, *roles: str) -> None:
    if user.global_role != "admin" and user.global_role not in roles:
        raise forbidden()


def get_membership(db: Session, project_id: str, user_id: str) -> ProjectMember | None:
    return db.get(ProjectMember, {"project_id": project_id, "user_id": user_id})


def project_access(
    db: Session, project_id: str, user: User, action: str = "read"
) -> tuple[Project, ProjectMember | None]:
    project = db.get(Project, project_id)
    if project is None or project.status == "archived" and action != "read":
        raise not_found("项目")
    membership = get_membership(db, project_id, user.id)
    if user.global_role != "admin" and membership is None:
        raise not_found("项目")
    if action == "read":
        return project, membership
    if user.global_role == "admin":
        return project, membership
    allowed = False
    if action == "edit":
        allowed = user.global_role == "editor" or (
            membership is not None and membership.project_role == "editor"
        )
    elif action == "review":
        allowed = user.global_role == "reviewer" or (
            membership is not None and membership.project_role == "reviewer"
        )
    elif action == "review_export":
        allowed = user.global_role in {"editor", "reviewer"} or (
            membership is not None and membership.project_role in {"editor", "reviewer"}
        )
    elif action == "create":
        allowed = user.global_role == "editor"
    if not allowed:
        raise forbidden()
    return project, membership


def can_read_project(db: Session, project_id: str, user: User) -> bool:
    if user.global_role == "admin":
        return db.get(Project, project_id) is not None
    return get_membership(db, project_id, user.id) is not None


def visible_projects_query(user: User):
    statement = select(Project)
    if user.global_role != "admin":
        statement = statement.join(ProjectMember).where(ProjectMember.user_id == user.id)
    return statement
