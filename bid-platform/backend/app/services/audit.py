from typing import Any

from sqlalchemy.orm import Session

from app.models.project import Activity


def record_activity(
    db: Session,
    actor_id: str | None,
    action: str,
    entity_type: str,
    entity_id: str,
    project_id: str | None = None,
    detail: dict[str, Any] | None = None,
) -> None:
    db.add(
        Activity(
            project_id=project_id,
            actor_id=actor_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail_json=detail or {},
        )
    )
