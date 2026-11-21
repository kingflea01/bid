from fastapi import APIRouter
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.serializers import snapshot_dict
from app.core.permissions import project_access
from app.models.section import ProjectSnapshot
from app.schemas.export import SnapshotCreate
from app.services.audit import record_activity
from app.services.persistence import commit
from app.services.workspace.snapshots import create_snapshot
from app.services.workspace.state import check_project_version, touch_project

router = APIRouter(prefix="/projects", tags=["snapshots"])


@router.post("/{project_id}/snapshots", status_code=201)
def create(project_id: str, payload: SnapshotCreate, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user, "edit")
    check_project_version(project, payload.version)
    snapshot = create_snapshot(db, project, user.id, payload.label)
    touch_project(db, project)
    record_activity(
        db,
        user.id,
        "snapshot.created",
        "project_snapshot",
        snapshot.id,
        project.id,
        {"snapshot_no": snapshot.snapshot_no, "state_hash": snapshot.state_hash},
    )
    commit(db)
    return snapshot_dict(db, snapshot)


@router.get("/{project_id}/snapshots")
def list_snapshots(project_id: str, db: DB, user: CurrentUser):
    project, _ = project_access(db, project_id, user)
    records = db.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project.id)
        .order_by(ProjectSnapshot.snapshot_no.desc())
    ).all()
    return [snapshot_dict(db, snapshot) for snapshot in records]
