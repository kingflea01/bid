from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.section import ProjectSection, ProjectSectionRevision
from app.services.workspace.content import fact_keys


def mark_fact_dependents(db: Session, project_id: str, changed_fact_key: str) -> list[str]:
    affected = []
    sections = db.scalars(
        select(ProjectSection).where(ProjectSection.project_id == project_id)
    ).all()
    for section in sections:
        if not section.selected_revision_id:
            continue
        revision = db.get(ProjectSectionRevision, section.selected_revision_id)
        if revision and changed_fact_key in fact_keys(revision.content_json):
            section.review_status = "needs_review"
            section.version += 1
            affected.append(section.id)
    return affected
