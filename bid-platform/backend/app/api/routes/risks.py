from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import risk_dict, score_dict
from app.core.errors import not_found
from app.core.permissions import project_access
from app.models.risk import Risk, ScoreAssessment
from app.schemas.section import RiskDisposition
from app.services.audit import record_activity
from app.services.persistence import commit
from app.services.workspace.state import check_project_version, touch_project

router = APIRouter(tags=["risks"])


@router.get("/projects/{project_id}/risks")
def list_risks(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    return [
        risk_dict(db, risk)
        for risk in db.scalars(select(Risk).where(Risk.project_id == project.id)).all()
    ]


@router.get("/projects/{project_id}/score-assessments")
def list_scores(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    return [
        score_dict(db, score)
        for score in db.scalars(
            select(ScoreAssessment).where(ScoreAssessment.project_id == project.id)
        ).all()
    ]


@router.post("/risks/{risk_id}:disposition")
def disposition(risk_id: str, payload: RiskDisposition, db: DB, user: CurrentUser):
    risk = db.get(Risk, risk_id)
    if risk is None:
        raise not_found("风险")
    project, _ = project_access(db, risk.project_id, user, "review")
    check_project_version(project, payload.version)
    risk.disposition = payload.disposition
    risk.disposed_by = user.id
    risk.disposition_note = payload.resolution_note
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "risk.disposition",
        "risk",
        risk.id,
        project.id,
        {"disposition": payload.disposition, "note": payload.resolution_note},
    )
    commit(db)
    return risk_dict(db, risk)
