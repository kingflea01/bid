from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.errors import conflict
from app.models.project import Project


def check_project_version(project: Project, expected: int | None) -> None:
    if expected is not None and project.version != expected:
        raise conflict(
            "项目已被其他用户修改，请刷新后重试",
            {"expected_version": expected, "current_version": project.version},
        )


def touch_project(db: Session, project: Project) -> None:
    expected = project.version
    result = db.execute(
        update(Project)
        .where(Project.id == project.id, Project.version == expected)
        .values(version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        db.rollback()
        raise conflict("项目已被其他用户修改，请刷新后重试")
    project.version = expected + 1
    db.flush()
