from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.serializers import (
    activity_dict,
    export_readiness,
    fact_dict,
    job_dict,
    project_dict,
    requirement_dict,
    revision_dict,
    risk_dict,
    snapshot_dict,
)
from app.models.project import Activity, Job, Project
from app.models.risk import Risk
from app.models.section import (
    Gap,
    ProjectFact,
    ProjectSection,
    ProjectSectionRevision,
    ProjectSnapshot,
    SectionCandidate,
)
from app.models.tender import Requirement, TenderDocument
from app.services.persistence import model_dict, models_dict
from app.services.workspace.tree import display_numbers


def workspace_view(db: Session, project: Project) -> dict:
    sections = db.scalars(
        select(ProjectSection).where(ProjectSection.project_id == project.id)
    ).all()
    numbers = display_numbers(sections)
    candidates = db.scalars(
        select(SectionCandidate)
        .join(ProjectSection, ProjectSection.id == SectionCandidate.section_id)
        .where(ProjectSection.project_id == project.id, SectionCandidate.status == "active")
    ).all()
    candidate_counts: dict[str, int] = {}
    for candidate in candidates:
        candidate_counts[candidate.section_id] = candidate_counts.get(candidate.section_id, 0) + 1
    section_values = []
    by_parent = {}
    for section in sections:
        by_parent.setdefault(section.parent_id, []).append(section)
        value = model_dict(section)
        value["display_number"] = numbers.get(section.id)
        value["candidate_count"] = candidate_counts.get(section.id, 0)
        revision = (
            db.get(ProjectSectionRevision, section.selected_revision_id)
            if section.selected_revision_id
            else None
        )
        value["selected_revision"] = revision_dict(revision)
        section_values.append(value)

    def descendants(section_id: str):
        for child in by_parent.get(section_id, []):
            yield child
            yield from descendants(child.id)

    for value in section_values:
        if value["content_mode"] != "group":
            continue
        children = list(descendants(value["id"]))
        leaves = [child for child in children if child.content_mode != "group"]
        if leaves:
            value["review_status"] = (
                "needs_review"
                if any(child.review_status == "needs_review" for child in leaves)
                else "confirmed"
                if all(child.review_status == "confirmed" for child in leaves)
                else "unconfirmed"
            )
            value["content_status"] = (
                "gap"
                if any(child.content_status == "gap" for child in leaves)
                else "empty"
                if all(child.content_status == "empty" for child in leaves)
                else "ready"
            )
    gaps = db.scalars(
        select(Gap).where(Gap.project_id == project.id).order_by(Gap.created_at)
    ).all()
    risks = db.scalars(
        select(Risk).where(Risk.project_id == project.id).order_by(Risk.created_at)
    ).all()
    jobs = db.scalars(
        select(Job).where(Job.project_id == project.id).order_by(Job.created_at.desc()).limit(30)
    ).all()
    facts = db.scalars(
        select(ProjectFact)
        .where(ProjectFact.project_id == project.id)
        .order_by(ProjectFact.fact_key)
    ).all()
    documents = db.scalars(
        select(TenderDocument).where(TenderDocument.project_id == project.id)
    ).all()
    requirements = (
        db.scalars(
            select(Requirement)
            .where(Requirement.document_id.in_([document.id for document in documents]))
            .order_by(Requirement.code)
        ).all()
        if documents
        else []
    )
    activities = db.scalars(
        select(Activity)
        .where(Activity.project_id == project.id)
        .order_by(Activity.created_at.desc())
        .limit(100)
    ).all()
    snapshots = db.scalars(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project.id)
        .order_by(ProjectSnapshot.snapshot_no.desc())
        .limit(20)
    ).all()
    return {
        "project": project_dict(db, project),
        "sections": sorted(
            section_values,
            key=lambda value: [int(part) for part in value["display_number"].split(".")],
        ),
        "requirements": [requirement_dict(db, requirement) for requirement in requirements],
        "facts": [fact_dict(fact, project.version) for fact in facts],
        "gaps": models_dict(gaps),
        "risks": [risk_dict(db, risk) for risk in risks],
        "tasks": [job_dict(job) for job in jobs],
        "activities": [activity_dict(db, activity) for activity in activities],
        "snapshots": [snapshot_dict(db, snapshot) for snapshot in snapshots],
        "export_readiness": export_readiness(db, project),
        "summary": {
            "sections": len([section for section in sections if section.content_mode != "group"]),
            "unconfirmed": len(
                [
                    section
                    for section in sections
                    if section.content_mode != "group" and section.review_status != "confirmed"
                ]
            ),
            "open_gaps": len([gap for gap in gaps if gap.status == "open"]),
            "pending_risks": len([risk for risk in risks if risk.disposition == "pending"]),
        },
    }
