from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DB, CurrentUser
from app.api.routes.sections import section_context
from app.api.serializers import SOURCE_LABELS, frontend_blocks
from app.core.errors import not_found
from app.models.asset import Asset, AssetRevision, AssetVariant
from app.models.project import Project
from app.models.section import (
    ProjectSection,
    ProjectSectionRevision,
    SectionCandidate,
    SectionDependency,
)
from app.services.persistence import model_dict
from app.services.workspace.content import block_text, fact_keys
from app.services.workspace.diff import structured_diff
from app.services.workspace.versions import (
    asset_candidate_current,
    candidate_content,
    find_section_candidate,
)

router = APIRouter(prefix="/sections", tags=["candidates"])


def _candidate_view(db: DB, candidate: SectionCandidate) -> dict:
    result = {
        **model_dict(candidate),
        "rank_reasons": candidate.rank_reasons_json,
    }
    content, _ = candidate_content(db, candidate)
    result["content_json"] = frontend_blocks(content)
    section = db.get(ProjectSection, candidate.section_id)
    selected = (
        db.get(ProjectSectionRevision, section.selected_revision_id)
        if section.selected_revision_id
        else None
    )
    current = False
    if candidate.candidate_type == "asset":
        revision = db.get(AssetRevision, candidate.candidate_id)
        variant = db.get(AssetVariant, revision.variant_id)
        asset = db.get(Asset, variant.asset_id)
        result["asset"] = model_dict(asset)
        result["variant"] = model_dict(variant)
        result["asset_revision"] = model_dict(revision)
        result.update(
            {
                "name": asset.title,
                "title": variant.name,
                "revision_no": revision.revision_no,
                "revision_label": f"V{revision.revision_no} · {variant.name}",
                "source_label": f"{asset.title} · {variant.name}",
                "valid_from": asset.valid_from,
                "valid_to": asset.valid_to,
            }
        )
        current = bool(selected and selected.source_asset_revision_id == candidate.candidate_id)
    elif candidate.candidate_type in {"history", "manual"}:
        revision = db.get(ProjectSectionRevision, candidate.candidate_id)
        result["revision"] = model_dict(revision)
        result["revision_no"] = revision.revision_no
        if candidate.candidate_type == "history":
            source_section = db.get(ProjectSection, revision.section_id)
            source_project = db.get(Project, source_section.project_id)
            result.update(
                {
                    "name": f"{source_project.name} · {source_section.title}",
                    "title": source_section.title,
                    "revision_label": f"历史确认 V{revision.revision_no}",
                    "source_label": f"{source_project.name} · 历史最终确认版本",
                }
            )
            current = bool(
                selected and selected.source_history_revision_id == candidate.candidate_id
            )
        else:
            result.update(
                {
                    "name": "当前项目人工修订",
                    "title": section.title,
                    "revision_label": f"人工修订 V{revision.revision_no}",
                    "source_label": SOURCE_LABELS["manual"],
                }
            )
            current = bool(selected and selected.id == candidate.candidate_id)
    result["current"] = current
    if current:
        result["status"] = "selected"
    return result


@router.get("/{section_id}/candidates")
def candidates(section_id: str, db: DB, user: CurrentUser):
    section, _ = section_context(db, section_id, user)
    records = db.scalars(
        select(SectionCandidate)
        .where(SectionCandidate.section_id == section.id, SectionCandidate.status == "active")
        .order_by(SectionCandidate.rank_score.desc(), SectionCandidate.created_at)
    ).all()
    records = [
        candidate
        for candidate in records
        if candidate.candidate_type != "asset" or asset_candidate_current(db, candidate)
    ]
    result = [_candidate_view(db, candidate) for candidate in records]
    if result:
        result[0]["recommended"] = not result[0]["current"]
    return result


def _diff_rows(operations: list[dict]) -> list[dict]:
    rows = []
    for operation in operations:
        op = operation["op"]
        before = operation.get("before", [])
        after = operation.get("after", [])
        if op == "equal":
            for block in before:
                rows.append(
                    {
                        "type": "unchanged",
                        "before_text": block_text(block),
                        "after_text": block_text(block),
                        "before": block,
                        "after": block,
                    }
                )
            continue
        paired = max(len(before), len(after))
        for index in range(paired):
            old = before[index] if index < len(before) else None
            new = after[index] if index < len(after) else None
            change_type = (
                "modified"
                if old is not None and new is not None
                else "removed"
                if old is not None
                else "added"
            )
            rows.append(
                {
                    "type": change_type,
                    "before_text": block_text(old) if old else "",
                    "after_text": block_text(new) if new else "",
                    "before": old,
                    "after": new,
                }
            )
    return rows


@router.get("/{section_id}/diff")
def diff(section_id: str, db: DB, user: CurrentUser, candidate_id: str = Query(...)):
    section, _ = section_context(db, section_id, user)
    candidate = find_section_candidate(db, section.id, candidate_id)
    if candidate is None:
        raise not_found("候选版本")
    after, _ = candidate_content(db, candidate)
    current = None
    if section.selected_revision_id:
        current = db.get(ProjectSectionRevision, section.selected_revision_id)
    before = current.content_json if current else []
    core = structured_diff(before, after)
    operations = []
    for operation in core["operations"]:
        i1, i2 = operation["before_indices"]
        j1, j2 = operation["after_indices"]
        operations.append(
            {
                **operation,
                "before": before[i1:i2],
                "after": after[j1:j2],
            }
        )
    impacted = db.scalars(
        select(ProjectSection)
        .join(SectionDependency, SectionDependency.section_id == ProjectSection.id)
        .where(SectionDependency.depends_on_section_id == section.id)
    ).all()
    before_facts = fact_keys(before)
    after_facts = fact_keys(after)
    fact_changes = [
        {
            "fact_key": key,
            "before": key in before_facts,
            "after": key in after_facts,
        }
        for key in sorted(before_facts.symmetric_difference(after_facts))
    ]
    candidate_view = _candidate_view(db, candidate)
    response = {
        "section_id": section.id,
        "candidate_id": candidate.id,
        "current_revision_id": current.id if current else None,
        "candidate_revision_id": candidate.candidate_id,
        "current_label": f"当前工作版本 V{current.revision_no}" if current else "当前空版本",
        "candidate_label": candidate_view.get("revision_label")
        or candidate_view.get("name")
        or candidate.candidate_type,
        "changes": _diff_rows(operations),
        "impacted_sections": [
            {"id": dependent.id, "title": dependent.title} for dependent in impacted
        ],
        "fact_changes": fact_changes,
    }
    return {**response, "diff": core}
