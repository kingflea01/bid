from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.asset import Asset, AssetAttachment, AssetRevision, AssetVariant
from app.models.project import Project, ProjectAttachment
from app.models.section import ProjectSnapshot
from app.models.tender import StoredFile, TenderOutline
from app.services.workspace.content import fact_keys, placeholders
from app.services.workspace.snapshots import snapshot_matches_current


def evaluate_snapshot_qa(
    db: Session, project: Project, snapshot: ProjectSnapshot, export_kind: str
) -> dict[str, Any]:
    tree = snapshot.tree_json
    revisions = snapshot.selected_revisions_json
    leaves = [
        node
        for node in tree
        if node["content_mode"] != "group" and node.get("mapping_status") != "omitted"
    ]
    placeholder_items = []
    missing_facts = []
    for node in leaves:
        revision = revisions.get(node["id"])
        content = revision["content_json"] if revision else []
        for value in placeholders(content):
            placeholder_items.append({"section_id": node["id"], "placeholder": value})
        for key in fact_keys(content):
            fact = snapshot.facts_json.get(key)
            if not fact or fact["status"] != "confirmed" or fact["value"] in (None, ""):
                missing_facts.append({"section_id": node["id"], "fact_key": key})
    unconfirmed = [node["id"] for node in leaves if node["review_status"] != "confirmed"]
    omitted_section_ids = {node["id"] for node in tree if node.get("mapping_status") == "omitted"}
    open_gaps = [
        gap
        for gap in snapshot.gaps_json
        if gap["status"] == "open"
        and gap["blocking"]
        and gap.get("section_id") not in omitted_section_ids
    ]
    pending_risks = [
        risk
        for risk in snapshot.risk_states_json
        if risk["disposition"] == "pending" or not risk.get("disposition_note")
    ]
    unconfirmed_facts = [
        key for key, fact in snapshot.facts_json.items() if fact["status"] != "confirmed"
    ]
    expired = []
    today = datetime.now(UTC).date()
    for revision in revisions.values():
        asset_revision_id = revision.get("source_asset_revision_id")
        if asset_revision_id:
            asset_revision = db.get(AssetRevision, asset_revision_id)
            variant = db.get(AssetVariant, asset_revision.variant_id) if asset_revision else None
            asset = db.get(Asset, variant.asset_id) if variant else None
            if (
                asset is None
                or asset.valid_from
                and asset.valid_from > today
                or asset.valid_to
                and asset.valid_to < today
            ):
                expired.append({"asset_revision_id": asset_revision_id})
        for block in revision["content_json"]:
            if block.get("type") == "attachment_ref":
                file_id = block.get("file_id")
                stored = db.get(StoredFile, file_id)
                attachment = db.scalar(
                    select(AssetAttachment).where(AssetAttachment.file_id == file_id)
                )
                project_attachment = db.scalar(
                    select(ProjectAttachment).where(
                        ProjectAttachment.project_id == project.id,
                        ProjectAttachment.file_id == file_id,
                    )
                )
                expiry = (
                    attachment.valid_to
                    if attachment
                    else project_attachment.valid_to
                    if project_attachment
                    else None
                )
                if stored is None or expiry and expiry < today:
                    expired.append({"file_id": file_id})
    missing_formats = []
    docx_document_ids = {
        doc["id"]
        for doc in snapshot.document_states_json
        if doc["parser_version"].startswith("docx")
    }
    docx_source_anchors = set()
    if docx_document_ids:
        docx_source_anchors = set(
            db.scalars(
                select(TenderOutline.source_start_anchor).where(
                    TenderOutline.document_id.in_(docx_document_ids)
                )
            ).all()
        )
    for node in leaves:
        if (
            node["source_type"] != "tender"
            or node["content_mode"] != "tender_template"
            or node.get("source_anchor") not in docx_source_anchors
        ):
            continue
        revision = revisions.get(node["id"])
        refs = [
            block
            for block in (revision["content_json"] if revision else [])
            if block.get("type") == "tender_ooxml_ref"
        ]
        if not refs or any(block.get("document_id") not in docx_document_ids for block in refs):
            missing_formats.append(node["id"])
    source_anchors = {node.get("source_anchor") for node in tree if node.get("source_anchor")}
    for document in snapshot.document_states_json:
        outlines = db.scalars(
            select(TenderOutline).where(TenderOutline.document_id == document["id"])
        ).all()
        for outline in outlines:
            if outline.source_start_anchor and outline.source_start_anchor not in source_anchors:
                missing_formats.append(f"outline:{outline.id}")
    unconfirmed_documents = [
        doc["id"]
        for doc in snapshot.document_states_json
        if doc["status"] != "parsed" or not doc["user_confirmed"]
    ]
    blockers = []

    def block(code: str, message: str, entities: list) -> None:
        if entities:
            blockers.append({"code": code, "message": message, "entities": entities})

    if export_kind == "formal":
        block("unconfirmed_sections", "存在未确认内容章节", unconfirmed)
        block("open_blocking_gaps", "存在未关闭阻塞缺口", [gap["id"] for gap in open_gaps])
        block(
            "pending_risks", "存在未处置风险或缺少处置意见", [risk["id"] for risk in pending_risks]
        )
        block("placeholders", "存在未填写字段、附件或内容占位符", placeholder_items)
        block(
            "unconfirmed_facts",
            "统一事实字段未确认",
            sorted(set(unconfirmed_facts + [item["fact_key"] for item in missing_facts])),
        )
        block("expired_assets", "使用了缺失、尚未生效或已过期的素材/附件", expired)
        block("tender_format_missing", "必要招标格式块缺失", sorted(set(missing_formats)))
        block("parse_not_confirmed", "招标解析尚未人工确认", unconfirmed_documents)
        if not snapshot_matches_current(db, project, snapshot):
            blockers.append(
                {
                    "code": "snapshot_stale",
                    "message": "项目当前状态与快照不一致",
                    "entities": [snapshot.id],
                }
            )
    return {
        "passed": not blockers,
        "export_kind": export_kind,
        "snapshot_id": snapshot.id,
        "snapshot_no": snapshot.snapshot_no,
        "snapshot_hash": snapshot.state_hash,
        "blockers": blockers,
        "stats": {
            "content_sections": len(leaves),
            "unconfirmed_sections": len(unconfirmed),
            "open_gaps": len(open_gaps),
            "open_blocking_gaps": len([gap for gap in open_gaps if gap["blocking"]]),
            "pending_risks": len(pending_risks),
            "placeholders": len(placeholder_items),
            "expired_assets": len(expired),
            "unconfirmed_facts": len(unconfirmed_facts),
        },
    }
