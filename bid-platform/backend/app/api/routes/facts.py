from datetime import date

from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import fact_dict
from app.core.errors import bad_request
from app.core.permissions import project_access
from app.models.section import ProjectFact
from app.schemas.section import FactUpdate
from app.services.audit import record_activity
from app.services.persistence import commit
from app.services.workspace.facts import mark_fact_dependents
from app.services.workspace.state import check_project_version, touch_project

router = APIRouter(tags=["facts"])


@router.patch("/projects/{project_id}/facts/{fact_key}")
def update_fact(project_id: str, fact_key: str, payload: FactUpdate, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    if payload.status == "confirmed":
        project_access(db, project_id, user, "review")
    check_project_version(project, payload.version)
    fact = db.scalar(
        select(ProjectFact).where(
            ProjectFact.project_id == project.id, ProjectFact.fact_key == fact_key
        )
    )
    if fact is None:
        fact = ProjectFact(
            project_id=project.id,
            fact_key=fact_key,
            value_json=payload.value,
            value_type=payload.value_type,
        )
        db.add(fact)
        db.flush()
    if payload.value_type == "number" and (
        isinstance(payload.value, bool) or not isinstance(payload.value, (int, float))
    ):
        raise bad_request("事实值应为数值")
    if payload.value_type == "boolean" and not isinstance(payload.value, bool):
        raise bad_request("事实值应为布尔值")
    if payload.value_type == "date":
        try:
            date.fromisoformat(str(payload.value))
        except ValueError as exc:
            raise bad_request("事实值应为 ISO 日期") from exc
    fact.value_json = payload.value
    fact.value_type = payload.value_type
    fact.status = payload.status
    fact.source_type = "manual"
    fact.source_id = user.id
    fact.confirmed_by = user.id if payload.status == "confirmed" else None
    affected = mark_fact_dependents(db, project.id, fact_key)
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "fact.updated",
        "project_fact",
        fact.id,
        project.id,
        {"fact_key": fact_key, "affected_section_ids": affected, "status": fact.status},
    )
    commit(db)
    serialized = fact_dict(fact, project.version)
    return {
        **serialized,
        "fact": serialized,
        "affected_section_ids": affected,
    }
