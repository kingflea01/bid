import copy
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import utcnow
from app.core.errors import bad_request, not_found
from app.models.config import TemplateRevision
from app.models.project import Project, ProjectConfigRef
from app.models.section import ProjectFact, ProjectSection
from app.models.tender import StoredFile, TenderBlock, TenderDocument, TenderOutline
from app.services.assets.repository import add_history_candidates, rebuild_asset_candidates
from app.services.audit import record_activity
from app.services.documents.docx_parser import parse_docx
from app.services.documents.pdf_parser import parse_pdf
from app.services.files.store import FileStore
from app.services.persistence import model_dict
from app.services.structure.merge import merge_trees, tender_tree
from app.services.structure.rules import normalize_terminology, walk_nodes
from app.services.workspace.state import touch_project
from app.services.workspace.versions import create_revision


def _cached_parse(db: Session, document: TenderDocument) -> dict[str, Any] | None:
    source = db.scalar(
        select(TenderDocument)
        .where(
            TenderDocument.sha256 == document.sha256,
            TenderDocument.id != document.id,
            TenderDocument.status == "parsed",
            TenderDocument.parser_version == document.parser_version,
        )
        .limit(1)
    )
    if source is None:
        return None
    blocks = db.scalars(
        select(TenderBlock)
        .where(TenderBlock.document_id == source.id)
        .order_by(TenderBlock.order_no)
    ).all()
    outlines = db.scalars(select(TenderOutline).where(TenderOutline.document_id == source.id)).all()
    result = {
        "blocks": [model_dict(block) for block in blocks],
        "outline": [model_dict(item) for item in outlines],
        "metadata": source.parse_qa_json.get("metadata", {}),
        "qa": copy.deepcopy(source.parse_qa_json),
        "page_count": source.page_count,
        "scanned_pages": copy.deepcopy(source.scanned_pages_json),
        "parser_version": source.parser_version,
        "cache_hit": True,
    }
    result["outline"].sort(
        key=lambda item: next(
            (
                block["order_no"]
                for block in result["blocks"]
                if block["anchor_key"] == item["source_start_anchor"]
            ),
            0,
        )
    )
    return result


def _persist_parse(db: Session, document: TenderDocument, parsed: dict[str, Any]) -> None:
    if parsed.get("cache_hit"):
        for raw in parsed["blocks"]:
            values = {
                key: value
                for key, value in raw.items()
                if key
                in {
                    "anchor_key",
                    "block_type",
                    "order_no",
                    "page_no",
                    "paragraph_index",
                    "table_index",
                    "bbox_json",
                    "text",
                    "ooxml_path",
                    "style_json",
                }
            }
            db.add(TenderBlock(document_id=document.id, **values))
        old_to_new = {}
        for raw in parsed["outline"]:
            values = {
                key: value
                for key, value in raw.items()
                if key
                in {
                    "position",
                    "title",
                    "level",
                    "source_start_anchor",
                    "source_end_anchor",
                    "recognition_confidence",
                }
            }
            values["recognition_confidence"] = values.get(
                "recognition_confidence", values.pop("confidence", 0.7)
            )
            item = TenderOutline(document_id=document.id, **values)
            db.add(item)
            db.flush()
            old_to_new[raw["id"]] = item
        for raw in parsed["outline"]:
            if raw.get("parent_id"):
                old_to_new[raw["id"]].parent_id = old_to_new[raw["parent_id"]].id
    else:
        for raw in parsed["blocks"]:
            db.add(TenderBlock(document_id=document.id, **raw))
        parents = []
        sibling_positions = {}
        for raw in parsed["outline"]:
            level = raw["level"]
            while parents and parents[-1][0] >= level:
                parents.pop()
            parent_id = parents[-1][1].id if parents else None
            sibling_positions[parent_id] = sibling_positions.get(parent_id, 0) + 1
            item = TenderOutline(
                document_id=document.id,
                parent_id=parent_id,
                position=sibling_positions[parent_id] - 1,
                title=raw["title"],
                level=level,
                source_start_anchor=raw.get("source_start_anchor"),
                source_end_anchor=raw.get("source_end_anchor"),
                recognition_confidence=raw.get("confidence", 0.7),
            )
            db.add(item)
            db.flush()
            raw["id"] = item.id
            parents.append((level, item))
    document.page_count = parsed.get("page_count")
    document.scanned_pages_json = parsed.get("scanned_pages", [])
    document.parse_qa_json = {
        **parsed["qa"],
        "metadata": parsed.get("metadata", {}),
        "cache_hit": bool(parsed.get("cache_hit")),
    }
    document.status = "parsed"
    document.parsed_at = utcnow()


def _store_facts(db: Session, project: Project, metadata: dict[str, Any], document_id: str) -> None:
    for key, value in metadata.items():
        fact = db.scalar(
            select(ProjectFact).where(
                ProjectFact.project_id == project.id, ProjectFact.fact_key == key
            )
        )
        value_type = "number" if isinstance(value, (int, float)) else "string"
        if fact:
            fact.value_json = value
            fact.value_type = value_type
            fact.source_id = document_id
            fact.source_type = "tender"
            fact.status = "unconfirmed"
        else:
            db.add(
                ProjectFact(
                    project_id=project.id,
                    fact_key=key,
                    value_json=value,
                    value_type=value_type,
                    source_type="tender",
                    source_id=document_id,
                )
            )


def _build_skeleton(
    db: Session,
    project: Project,
    document: TenderDocument,
    parsed: dict[str, Any],
    actor_id: str | None,
) -> dict[str, Any]:
    existing = db.scalar(
        select(ProjectSection.id).where(ProjectSection.project_id == project.id).limit(1)
    )
    if existing:
        raise bad_request("项目已有章节，不能重复生成骨架", code="workspace_already_exists")
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    template = db.get(TemplateRevision, refs.template_revision_id)
    full_text = "\n".join(block["text"] for block in parsed["blocks"])
    response_term = "响应" if "响应文件" in full_text else "投标"
    award_term = "成交" if "成交" in full_text else "中标"
    template_nodes = copy.deepcopy(template.nodes_json)
    for node in walk_nodes(template_nodes):
        node["title"] = normalize_terminology(node.get("title", ""), response_term, award_term)
    merged = merge_trees(tender_tree(parsed["outline"]), template_nodes)
    if not merged["nodes"]:
        merged = merge_trees(
            [], [{"title": f"{response_term}文件", "content_mode": "placeholder", "children": []}]
        )
    stats = merged["stats"]
    stats["cache_key"] = hashlib.sha256(
        json.dumps(
            {
                "sha256": document.sha256,
                "package": project.package,
                "template_revision_id": template.id,
                "parser_version": parsed["parser_version"],
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()
    document.parse_qa_json = {
        **document.parse_qa_json,
        "structure": stats,
        "mapping_ambiguities": merged["ambiguities"],
    }
    anchor_orders = {block["anchor_key"]: block["order_no"] for block in parsed["blocks"]}

    def persist_node(raw: dict[str, Any], parent_id: str | None, position: int) -> ProjectSection:
        section = ProjectSection(
            project_id=project.id,
            parent_id=parent_id,
            position=position,
            title=raw["title"],
            section_key=raw["section_key"],
            source_type=raw["source"],
            locked=raw.get("locked", False),
            content_mode=raw.get("content_mode", "placeholder"),
            source_anchor=raw.get("source_start_anchor"),
            source_end_anchor=raw.get("source_end_anchor"),
            mapping_status=raw.get("mapping_status", "resolved"),
        )
        db.add(section)
        db.flush()
        content = copy.deepcopy(raw.get("content_json") or [])
        if raw["source"] == "tender" and raw.get("source_start_anchor"):
            start = anchor_orders.get(raw["source_start_anchor"], -1)
            end = anchor_orders.get(raw.get("source_end_anchor"), len(parsed["blocks"]))
            has_source_blocks = any(start < order < end for order in anchor_orders.values())
            if has_source_blocks and document.parser_version.startswith("docx"):
                content = [
                    {
                        "type": "tender_ooxml_ref",
                        "document_id": document.id,
                        "anchor_key": raw["source_start_anchor"],
                        "end_anchor_key": raw.get("source_end_anchor"),
                    }
                ]
            elif has_source_blocks:
                title = f"按招标文件格式填写：{raw['title']}"
                content = [
                    {
                        "type": "placeholder",
                        "kind": "content",
                        "name": title,
                        "text": f"[[{title}]]",
                    }
                ]
        if not content and not raw.get("children"):
            title = f"待编写：{raw['title']}"
            content = [
                {"type": "placeholder", "kind": "content", "name": title, "text": f"[[{title}]]"}
            ]
        if content:
            create_revision(
                db,
                section,
                content,
                "tender" if raw["source"] == "tender" else "template",
                actor_id,
            )
        else:
            section.content_mode = "group"
            section.content_status = "empty"
        for index, child in enumerate(raw.get("children", [])):
            persist_node(child, section.id, index)
        rebuild_asset_candidates(db, project, section)
        add_history_candidates(db, project, section)
        return section

    for index, node in enumerate(merged["nodes"]):
        persist_node(node, None, index)
    project.status = "workspace"
    return stats


def parse_project_document(
    db: Session, project_id: str, document_id: str, actor_id: str | None = None
) -> dict[str, Any]:
    project = db.get(Project, project_id)
    document = db.get(TenderDocument, document_id)
    stored = db.get(StoredFile, document.file_id) if document else None
    if project is None or document is None or stored is None or document.project_id != project.id:
        raise not_found("招标文档")
    suffix = Path(stored.original_name).suffix.lower()
    document.parser_version = "pdf-v1" if suffix == ".pdf" else "docx-v1"
    document.status = "parsing"
    db.commit()
    try:
        parse_started = time.perf_counter()
        parsed = _cached_parse(db, document)
        if parsed is None:
            path = FileStore().path_for(stored)
            parsed = parse_pdf(path) if suffix == ".pdf" else parse_docx(path)
        _persist_parse(db, document, parsed)
        if suffix == ".pdf":
            document.user_confirmed = False
        else:
            document.user_confirmed = True
        _store_facts(db, project, parsed.get("metadata", {}), document.id)
        skeleton_started = time.perf_counter()
        stats = _build_skeleton(db, project, document, parsed, actor_id)
        timing = {
            "parse_ms": round((skeleton_started - parse_started) * 1000, 2),
            "skeleton_ms": round((time.perf_counter() - skeleton_started) * 1000, 2),
        }
        document.parse_qa_json = {**document.parse_qa_json, "timing": timing}
        documents = db.scalars(
            select(TenderDocument).where(
                TenderDocument.project_id == project.id, TenderDocument.status == "parsed"
            )
        ).all()
        project.parse_confirmed = bool(documents) and all(item.user_confirmed for item in documents)
        touch_project(db, project)
        record_activity(
            db,
            actor_id,
            "project.parsed",
            "tender_document",
            document.id,
            project.id,
            {"structure": stats, "cache_hit": bool(parsed.get("cache_hit"))},
        )
        db.commit()
        return {
            "document_id": document.id,
            "status": document.status,
            "structure": stats,
            "timing": timing,
            "parse_confirmed": project.parse_confirmed,
            "scanned_pages": document.scanned_pages_json,
        }
    except Exception:
        db.rollback()
        failed = db.get(TenderDocument, document_id)
        if failed:
            failed.status = "failed"
            db.commit()
        raise
