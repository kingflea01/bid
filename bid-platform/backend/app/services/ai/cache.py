import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.task import AIRun


def input_hash(task_type: str, manifest: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"task_type": task_type, **manifest},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cached_run(db: Session, task_type: str, digest: str) -> AIRun | None:
    return db.scalar(
        select(AIRun)
        .where(
            AIRun.task_type == task_type, AIRun.input_hash == digest, AIRun.status == "succeeded"
        )
        .order_by(AIRun.created_at.desc())
        .limit(1)
    )
