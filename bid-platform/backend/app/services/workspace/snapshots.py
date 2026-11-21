import hashlib
import json
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found
from app.models.project import Project, ProjectConfigRef
from app.models.risk import Risk
from app.models.section import (
    Gap,
    ProjectFact,
    ProjectSection,
    ProjectSectionRevision,
    ProjectSnapshot,
)
from app.models.tender import TenderDocument
from app.services.persistence import model_dict
from app.services.workspace.tree import display_numbers


def current_snapshot_state(db: Session, project: Project) -> dict[str, Any]:
    sections = db.scalars(
        select(ProjectSection).where(ProjectSection.project_id == project.id)
    ).all()
    numbers = display_numbers(sections)
    tree = []
    selected = {}
    for section in sections:
        tree.append(
            {
                "id": section.id,
                "parent_id": section.parent_id,
                "position": section.position,
                "display_number": numbers.get(section.id),
                "title": section.title,
                "section_key": section.section_key,
                "source_type": section.source_type,
                "source_anchor": section.source_anchor,
                "locked": section.locked,
                "content_mode": section.content_mode,
                "selected_revision_id": section.selected_revision_id,
                "content_status": section.content_status,
                "review_status": section.review_status,
                "mapping_status": section.mapping_status,
                "version": section.version,
            }
        )
        if section.selected_revision_id:
            revision = db.get(ProjectSectionRevision, section.selected_revision_id)
            if revision:
                selected[section.id] = {
                    "id": revision.id,
                    "revision_no": revision.revision_no,
                    "content_json": revision.content_json,
                    "source_type": revision.source_type,
                    "source_asset_revision_id": revision.source_asset_revision_id,
                    "source_history_revision_id": revision.source_history_revision_id,
                    "created_by": revision.created_by,
                }
    tree.sort(key=lambda item: [int(part) for part in item["display_number"].split(".")])
    facts = {
        fact.fact_key: {
            "value": fact.value_json,
            "value_type": fact.value_type,
            "status": fact.status,
            "source_type": fact.source_type,
            "source_id": fact.source_id,
            "confirmed_by": fact.confirmed_by,
        }
        for fact in db.scalars(
            select(ProjectFact).where(ProjectFact.project_id == project.id)
        ).all()
    }
    risks = [
        model_dict(risk)
        for risk in db.scalars(
            select(Risk).where(Risk.project_id == project.id).order_by(Risk.created_at)
        ).all()
    ]
    gaps = [
        model_dict(gap)
        for gap in db.scalars(
            select(Gap).where(Gap.project_id == project.id).order_by(Gap.created_at)
        ).all()
    ]
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    documents = [
        {
            "id": doc.id,
            "sha256": doc.sha256,
            "status": doc.status,
            "parser_version": doc.parser_version,
            "user_confirmed": doc.user_confirmed,
            "scanned_pages": doc.scanned_pages_json,
        }
        for doc in db.scalars(
            select(TenderDocument)
            .where(TenderDocument.project_id == project.id)
            .order_by(TenderDocument.created_at)
        ).all()
    ]
    state = {
        "tree_json": tree,
        "selected_revisions_json": selected,
        "facts_json": facts,
        "risk_states_json": risks,
        "gaps_json": gaps,
        "config_refs_json": model_dict(refs),
        "document_states_json": documents,
    }
    state["state_hash"] = state_hash(state)
    return state


def state_hash(state: dict[str, Any]) -> str:
    payload = {key: value for key, value in state.items() if key != "state_hash"}
    encoded = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def create_snapshot(
    db: Session, project: Project, actor_id: str, label: str | None = None
) -> ProjectSnapshot:
    state = current_snapshot_state(db, project)
    number = (
        db.scalar(
            select(func.max(ProjectSnapshot.snapshot_no)).where(
                ProjectSnapshot.project_id == project.id
            )
        )
        or 0
    ) + 1
    snapshot = ProjectSnapshot(
        project_id=project.id, snapshot_no=number, created_by=actor_id, label=label, **state
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def project_snapshot(db: Session, project: Project, snapshot_id: str) -> ProjectSnapshot:
    snapshot = db.get(ProjectSnapshot, snapshot_id)
    if snapshot is None or snapshot.project_id != project.id:
        raise not_found("项目快照")
    return snapshot


def snapshot_matches_current(db: Session, project: Project, snapshot: ProjectSnapshot) -> bool:
    return current_snapshot_state(db, project)["state_hash"] == snapshot.state_hash
