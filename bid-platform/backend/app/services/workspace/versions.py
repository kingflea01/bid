import copy
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import bad_request, not_found
from app.models.asset import Asset, AssetRevision, AssetVariant
from app.models.config import ProductRevision
from app.models.project import Project, ProjectConfigRef
from app.models.section import (
    Gap,
    ProjectSection,
    ProjectSectionRevision,
    SectionCandidate,
    SectionDependency,
)
from app.models.tender import TenderBlock, TenderDocument
from app.services.assets.ranking import asset_matches
from app.services.workspace.content import normalize_block_aliases, placeholders


def next_section_revision(db: Session, section_id: str) -> int:
    return (
        db.scalar(
            select(func.max(ProjectSectionRevision.revision_no)).where(
                ProjectSectionRevision.section_id == section_id
            )
        )
        or 0
    ) + 1


def sync_placeholder_gaps(
    db: Session, section: ProjectSection, content: list[dict[str, Any]]
) -> None:
    existing = db.scalars(
        select(Gap).where(
            Gap.section_id == section.id,
            Gap.status == "open",
            Gap.gap_type.in_(["content", "field", "attachment"]),
        )
    ).all()
    known = {gap.title for gap in existing}
    for value in placeholders(content):
        title = (
            value
            if value.startswith(("待编写：", "附件：", "按招标文件格式填写："))
            else f"字段：{value}"
        )
        if title not in known:
            gap_type = (
                "attachment"
                if value.startswith("附件：")
                else "content"
                if value.startswith(("待编写：", "按招标文件格式填写："))
                else "field"
            )
            db.add(
                Gap(
                    project_id=section.project_id,
                    section_id=section.id,
                    gap_type=gap_type,
                    title=title,
                    blocking=True,
                )
            )
            known.add(title)


def create_revision(
    db: Session,
    section: ProjectSection,
    content: list[dict[str, Any]],
    source_type: str,
    actor_id: str | None,
    source_asset_revision_id: str | None = None,
    source_history_revision_id: str | None = None,
    make_manual_candidate: bool = False,
) -> ProjectSectionRevision:
    content = normalize_block_aliases(content)
    revision = ProjectSectionRevision(
        section_id=section.id,
        revision_no=next_section_revision(db, section.id),
        content_json=copy.deepcopy(content),
        source_type=source_type,
        source_asset_revision_id=source_asset_revision_id,
        source_history_revision_id=source_history_revision_id,
        created_by=actor_id,
    )
    db.add(revision)
    db.flush()
    section.selected_revision_id = revision.id
    section.content_status = "empty" if not content else "gap" if placeholders(content) else "ready"
    section.review_status = "unconfirmed"
    section.version += 1
    sync_placeholder_gaps(db, section, content)
    if make_manual_candidate:
        db.add(
            SectionCandidate(
                section_id=section.id,
                candidate_type="manual",
                candidate_id=revision.id,
                rank_score=10,
                rank_reasons_json=["当前项目人工修订版本"],
            )
        )
    return revision


def find_section_candidate(
    db: Session, section_id: str, candidate_id: str
) -> SectionCandidate | None:
    candidate = db.get(SectionCandidate, candidate_id)
    if candidate is None or candidate.section_id != section_id:
        candidate = db.scalar(
            select(SectionCandidate).where(
                SectionCandidate.section_id == section_id,
                SectionCandidate.candidate_id == candidate_id,
            )
        )
    return candidate


def asset_candidate_current(db: Session, candidate: SectionCandidate) -> bool:
    revision = db.get(AssetRevision, candidate.candidate_id)
    variant = db.get(AssetVariant, revision.variant_id) if revision else None
    asset = db.get(Asset, variant.asset_id) if variant else None
    section = db.get(ProjectSection, candidate.section_id)
    project = db.get(Project, section.project_id) if section else None
    refs = (
        db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
        if project
        else None
    )
    product_revision = db.get(ProductRevision, refs.product_revision_id) if refs else None
    return bool(
        revision
        and revision.status == "published"
        and asset
        and product_revision
        and asset_matches(
            asset, project, product_revision.product_id, section.title, section.section_key
        )
    )


def validate_tender_references(
    db: Session, section: ProjectSection, content: list[dict[str, Any]]
) -> None:
    for block in content:
        if block.get("type") != "tender_ooxml_ref":
            continue
        if not block.get("document_id") and block.get("anchor_key"):
            candidates = db.scalars(
                select(TenderDocument)
                .join(TenderBlock, TenderBlock.document_id == TenderDocument.id)
                .where(
                    TenderDocument.project_id == section.project_id,
                    TenderBlock.anchor_key == block["anchor_key"],
                )
            ).all()
            if len(candidates) == 1:
                block["document_id"] = candidates[0].id
        document = db.get(TenderDocument, block.get("document_id"))
        if document is None or document.project_id != section.project_id:
            raise not_found("招标 OOXML 来源")
        for key in ("anchor_key", "end_anchor_key"):
            anchor_key = block.get(key)
            if (
                anchor_key
                and db.scalar(
                    select(TenderBlock.id).where(
                        TenderBlock.document_id == document.id,
                        TenderBlock.anchor_key == anchor_key,
                    )
                )
                is None
            ):
                raise bad_request("OOXML 锚点不属于当前招标文档", code="invalid_tender_anchor")


def _history_content(
    db: Session, candidate: SectionCandidate, revision: ProjectSectionRevision
) -> list[dict[str, Any]]:
    section = db.get(ProjectSection, candidate.section_id)
    source_section = db.get(ProjectSection, revision.section_id)
    project = db.get(Project, section.project_id)
    source_project = db.get(Project, source_section.project_id)
    if (
        project.source_project_id != source_project.id
        or project.customer_name != source_project.customer_name
    ):
        raise not_found("历史候选")
    current_ref = None
    if section.selected_revision_id:
        current = db.get(ProjectSectionRevision, section.selected_revision_id)
        current_ref = next(
            (
                copy.deepcopy(block)
                for block in current.content_json
                if block.get("type") == "tender_ooxml_ref"
            ),
            None,
        )
    content = []
    for raw in revision.content_json:
        block = copy.deepcopy(raw)
        if block.get("type") == "tender_ooxml_ref":
            if current_ref is not None:
                block = copy.deepcopy(current_ref)
            else:
                title = f"按招标文件格式填写：{section.title}"
                block = {
                    "type": "placeholder",
                    "kind": "content",
                    "name": title,
                    "text": f"[[{title}]]",
                }
        elif block.get("type") == "attachment_ref":
            title = f"附件：{block.get('name', '历史附件')}"
            block = {
                "type": "placeholder",
                "kind": "attachment",
                "name": title,
                "text": f"[[{title}]]",
            }
        content.append(block)
    return content


def candidate_content(
    db: Session, candidate: SectionCandidate
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if candidate.candidate_type == "asset":
        revision = db.get(AssetRevision, candidate.candidate_id)
        if revision is None or not asset_candidate_current(db, candidate):
            raise not_found("素材候选")
        return copy.deepcopy(revision.content_json), {
            "source_asset_revision_id": revision.id,
            "source_history_revision_id": None,
        }
    revision = db.get(ProjectSectionRevision, candidate.candidate_id)
    if revision is None:
        raise not_found("章节候选")
    if candidate.candidate_type == "history":
        return _history_content(db, candidate, revision), {
            "source_asset_revision_id": None,
            "source_history_revision_id": revision.id,
        }
    if candidate.candidate_type == "manual" and revision.section_id != candidate.section_id:
        raise bad_request("人工候选不属于当前章节")
    return copy.deepcopy(revision.content_json), {
        "source_asset_revision_id": revision.source_asset_revision_id,
        "source_history_revision_id": revision.source_history_revision_id,
    }


def select_candidate(
    db: Session, section: ProjectSection, candidate: SectionCandidate, actor_id: str
) -> ProjectSectionRevision:
    content, sources = candidate_content(db, candidate)
    validate_tender_references(db, section, content)
    revision = create_revision(db, section, content, candidate.candidate_type, actor_id, **sources)
    dependencies = db.scalars(
        select(SectionDependency).where(SectionDependency.depends_on_section_id == section.id)
    ).all()
    for dependency in dependencies:
        dependent = db.get(ProjectSection, dependency.section_id)
        if dependent and dependent.id != section.id and dependent.review_status == "confirmed":
            dependent.review_status = "needs_review"
            dependent.version += 1
    return revision
