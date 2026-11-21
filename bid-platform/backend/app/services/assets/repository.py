from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetRevision, AssetVariant
from app.models.config import ProductRevision
from app.models.project import Project, ProjectConfigRef
from app.models.section import ProjectSection, ProjectSectionRevision, SectionCandidate
from app.services.assets.ranking import asset_matches, rank_asset
from app.services.structure.rules import titles_match


def rebuild_asset_candidates(db: Session, project: Project, section: ProjectSection) -> None:
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    if refs is None:
        return
    product_revision = db.get(ProductRevision, refs.product_revision_id)
    product_id = product_revision.product_id
    rows = db.execute(
        select(Asset, AssetRevision)
        .join(AssetVariant, AssetVariant.asset_id == Asset.id)
        .join(AssetRevision, AssetRevision.variant_id == AssetVariant.id)
        .where(AssetRevision.status == "published", AssetVariant.status == "published")
    ).all()
    existing = db.scalars(
        select(SectionCandidate).where(
            SectionCandidate.section_id == section.id, SectionCandidate.candidate_type == "asset"
        )
    ).all()
    for candidate in existing:
        db.delete(candidate)
    for asset, revision in rows:
        if not asset_matches(asset, project, product_id, section.title, section.section_key):
            continue
        score, reasons = rank_asset(asset, revision, project, product_id)
        db.add(
            SectionCandidate(
                section_id=section.id,
                candidate_type="asset",
                candidate_id=revision.id,
                rank_score=score,
                rank_reasons_json=reasons,
            )
        )


def add_history_candidates(db: Session, project: Project, section: ProjectSection) -> None:
    if not project.source_project_id:
        return
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    source_refs = db.scalar(
        select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.source_project_id)
    )
    if not refs or not source_refs:
        return
    current_product = db.get(ProductRevision, refs.product_revision_id).product_id
    source_product = db.get(ProductRevision, source_refs.product_revision_id).product_id
    source_project = db.get(Project, project.source_project_id)
    if current_product != source_product or source_project.customer_name != project.customer_name:
        return
    source_sections = db.scalars(
        select(ProjectSection).where(
            ProjectSection.project_id == source_project.id,
            ProjectSection.review_status == "confirmed",
        )
    ).all()
    for source in source_sections:
        if not source.selected_revision_id or not titles_match(
            source.section_key, section.section_key
        ):
            continue
        revision = db.get(ProjectSectionRevision, source.selected_revision_id)
        if revision:
            db.add(
                SectionCandidate(
                    section_id=section.id,
                    candidate_type="history",
                    candidate_id=revision.id,
                    rank_score=120,
                    rank_reasons_json=["同客户、同产品的历史项目最终确认版本"],
                )
            )
