import io
import re
import zipfile
from typing import Any

import docx
import fitz
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError, bad_request
from app.models.project import Project
from app.models.section import ProjectSnapshot
from app.models.tender import StoredFile, TenderBlock, TenderDocument
from app.services.export.ooxml import (
    add_field,
    block_elements,
    clear_body,
    clone_elements,
    table_signature,
)
from app.services.files.store import FileStore
from app.services.structure.cleanup import clean_paragraph, clean_table, paragraph_text
from app.services.structure.rules import canonical
from app.services.workspace.content import PLACEHOLDER_RE


def _font(run, size: int = 12, bold: bool = False) -> None:
    run.font.size = Pt(size)
    run.bold = bold
    run.font.name = "宋体"
    properties = run._element.get_or_add_rPr()
    fonts = properties.find(qn("w:rFonts"))
    if fonts is None:
        fonts = OxmlElement("w:rFonts")
        properties.append(fonts)
    fonts.set(qn("w:ascii"), "Times New Roman")
    fonts.set(qn("w:hAnsi"), "Times New Roman")
    fonts.set(qn("w:eastAsia"), "宋体")


def _heading(document, title: str, level: int, page_break: bool = False) -> None:
    paragraph = document.add_paragraph()
    paragraph.paragraph_format.page_break_before = page_break
    paragraph.paragraph_format.keep_with_next = True
    paragraph.paragraph_format.space_before = Pt(12)
    paragraph.paragraph_format.space_after = Pt(6)
    _font(paragraph.add_run(title), 16 if level == 1 else 14 if level == 2 else 12, True)
    outline = OxmlElement("w:outlineLvl")
    outline.set(qn("w:val"), str(max(0, min(level - 1, 8))))
    paragraph._p.get_or_add_pPr().append(outline)


def _review_watermark(document) -> None:
    header = document.sections[0].header
    paragraph = header.paragraphs[0]
    run = paragraph.add_run()
    pict = OxmlElement("w:pict")
    shape = etree.Element("{urn:schemas-microsoft-com:vml}shape")
    shape.set("id", "BidReviewWatermark")
    shape.set("type", "#_x0000_t136")
    shape.set(
        "style",
        "position:absolute;margin-left:0;margin-top:0;width:500pt;height:100pt;rotation:315;z-index:-251654144;mso-position-horizontal:center;mso-position-vertical:center",
    )
    shape.set("fillcolor", "#C0C0C0")
    shape.set("stroked", "f")
    fill = etree.Element("{urn:schemas-microsoft-com:vml}fill")
    fill.set("opacity", ".18")
    textpath = etree.Element("{urn:schemas-microsoft-com:vml}textpath")
    textpath.set("style", "font-family:'宋体';font-size:1pt")
    textpath.set("string", "审阅版")
    shape.extend((fill, textpath))
    pict.append(shape)
    run._r.append(pict)


def _footer(document, snapshot_no: int) -> None:
    paragraph = document.sections[0].footer.paragraphs[0]
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _font(paragraph.add_run(f"快照 #{snapshot_no}  第 "), 9)
    add_field(paragraph, "PAGE", "1")
    _font(paragraph.add_run(" 页 / 共 "), 9)
    add_field(paragraph, "NUMPAGES", "1")
    _font(paragraph.add_run(" 页"), 9)


def _text(document, text: str, facts: dict[str, Any], size: int = 12, center: bool = False) -> None:
    paragraph = document.add_paragraph()
    if center:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for key, value in facts.items():
        if value is not None and not isinstance(value, (dict, list)):
            text = text.replace(f"[[{key}]]", str(value)).replace(f"[[字段：{key}]]", str(value))
    for part in re.split(r"(\[\[.+?\]\])", text):
        if not part:
            continue
        run = paragraph.add_run(part)
        _font(run, size)
        if part.startswith("[[") and part.endswith("]]"):
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW


def _cover(
    document,
    project: Project,
    snapshot: ProjectSnapshot,
    facts: dict[str, Any],
    export_kind: str,
    stats: dict[str, Any],
) -> None:
    for _ in range(4):
        document.add_paragraph()
    title = "响应文件" if facts.get("response_term") == "响应" else "投标文件"
    _text(document, title, facts, 26, True)
    if export_kind == "review":
        _text(document, "审 阅 版", facts, 20, True)
    for key, label, fallback in (
        ("project_name", "项目名称", project.name),
        ("project_number", "项目编号", project.code),
    ):
        _text(document, f"{label}：{facts.get(key) or fallback}", facts, 14, True)
    _text(document, f"供应商：{facts.get('supplier_name') or '[[供应商名称]]'}", facts, 14, True)
    _text(document, f"日期：{facts.get('落款日期') or '[[落款日期]]'}", facts, 14, True)
    _text(document, f"项目快照：#{snapshot.snapshot_no}", facts, 11, True)
    if export_kind == "review":
        _text(
            document,
            f"未确认章节：{stats['unconfirmed_sections']}；未关闭缺口：{stats['open_gaps']}；待处置风险：{stats['pending_risks']}",
            facts,
            11,
            True,
        )
    document.add_page_break()
    _heading(document, "目录", 1)
    paragraph = document.add_paragraph()
    add_field(paragraph, 'TOC \\o "1-3" \\h \\z \\u', "目录将在 Word 中更新后显示")
    document.add_page_break()


def _facts(snapshot: ProjectSnapshot, project: Project) -> dict[str, Any]:
    facts = {key: item["value"] for key, item in snapshot.facts_json.items()}
    aliases = {
        "公司名称": "supplier_name",
        "供应商名称": "supplier_name",
        "legal_name": "supplier_name",
        "统一社会信用代码": "credit_code",
        "unified_social_credit_code": "credit_code",
        "注册地址": "registered_address",
        "法定代表人": "legal_rep",
        "成立时间": "established",
        "注册资本": "capital",
        "主营业务": "main_business",
    }
    for source, target in aliases.items():
        if source in facts and facts[source] and not facts.get(target):
            facts[target] = facts[source]
    facts.setdefault("project_name", project.name)
    facts.setdefault("project_number", project.code)
    return facts


def _render_table(document, rows: list[list[Any]], facts: dict[str, Any]) -> None:
    if not rows:
        return
    width = max(len(row) for row in rows)
    table = document.add_table(rows=0, cols=width)
    table.style = "Table Grid"
    for raw_row in rows:
        cells = table.add_row().cells
        for index, value in enumerate(raw_row):
            text = str(value)
            for key, fact in facts.items():
                if fact is not None and not isinstance(fact, (dict, list)):
                    text = text.replace(f"[[{key}]]", str(fact))
            cells[index].text = text


def _render_attachment(document, db: Session, block: dict[str, Any]) -> None:
    stored = db.get(StoredFile, block.get("file_id"))
    if stored is None:
        _text(document, f"[[附件：{block.get('name', '缺失附件')}]]", {})
        return
    data = FileStore().read(stored)
    suffix = stored.original_name.lower().rsplit(".", 1)[-1]
    paragraph = document.add_paragraph()
    _font(paragraph.add_run(f"附件：{block.get('name') or stored.original_name}"), 12, True)
    if suffix in {"png", "jpg", "jpeg"}:
        document.add_picture(io.BytesIO(data), width=Inches(6.0))
    elif suffix == "pdf":
        with fitz.open(stream=data, filetype="pdf") as pdf:
            for index, page in enumerate(pdf):
                image = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False).tobytes("png")
                document.add_picture(io.BytesIO(image), width=Inches(6.0))
                if index + 1 < len(pdf):
                    document.add_page_break()
    else:
        raise AppError(422, "unsupported_attachment_format", "DOCX 附件请转换为 PDF 或图片后上传")


def _source_document(db: Session, document_id: str, cache: dict[str, Any]):
    if document_id not in cache:
        tender = db.get(TenderDocument, document_id)
        stored = db.get(StoredFile, tender.file_id) if tender else None
        if tender is None or stored is None or not tender.parser_version.startswith("docx"):
            raise bad_request("招标 OOXML 来源无效", code="tender_format_missing")
        cache[document_id] = docx.Document(str(FileStore().path_for(stored)))
    return cache[document_id]


def _render_ooxml(
    document,
    db: Session,
    node: dict[str, Any],
    block: dict[str, Any],
    facts: dict[str, Any],
    source_cache: dict[str, Any],
    cleanup: list[dict[str, Any]],
    errors: list[str],
    has_children: bool,
) -> None:
    source = _source_document(db, block["document_id"], source_cache)
    start = db.scalar(
        select(TenderBlock).where(
            TenderBlock.document_id == block["document_id"],
            TenderBlock.anchor_key == block["anchor_key"],
        )
    )
    end = (
        db.scalar(
            select(TenderBlock).where(
                TenderBlock.document_id == block["document_id"],
                TenderBlock.anchor_key == block.get("end_anchor_key"),
            )
        )
        if block.get("end_anchor_key")
        else None
    )
    elements = block_elements(
        source, start.paragraph_index if start else None, end.paragraph_index if end else None
    )
    if not elements:
        if not has_children:
            _text(document, f"[[待编写：{node['title']}]]", facts)
        errors.append(f"{node['id']}:missing_source_blocks")
        return
    expected_tables = [
        table_signature(element) for element in elements if element.tag == qn("w:tbl")
    ]
    cloned = clone_elements(document, elements)
    actual_tables = []
    kept = 0
    first_text = True
    for element in cloned:
        if element.tag == qn("w:p"):
            text = paragraph_text(element)
            if text and first_text:
                first_text = False
                if canonical(text) == canonical(node["title"]):
                    element.getparent().remove(element)
                    cleanup.append({"section_id": node["id"], "action": "remove_duplicate_title"})
                    continue
            action, _ = clean_paragraph(element, facts)
            if action == "remove":
                cleanup.append({"section_id": node["id"], "action": "remove_instruction"})
            else:
                kept += int(action != "empty")
        elif element.tag == qn("w:tbl"):
            clean_table(element)
            actual_tables.append(table_signature(element))
            kept += 1
    if expected_tables != actual_tables:
        errors.append(f"{node['id']}:table_structure_changed")
    if not kept and not has_children:
        _text(document, f"[[待编写：{node['title']}]]", facts)


def build_docx(
    db: Session,
    project: Project,
    snapshot: ProjectSnapshot,
    export_kind: str,
    qa: dict[str, Any],
    include_sources: bool = False,
) -> tuple[bytes, dict[str, Any]]:
    facts = _facts(snapshot, project)
    referenced_ids = {
        block.get("document_id")
        for revision in snapshot.selected_revisions_json.values()
        for block in revision["content_json"]
        if block.get("type") == "tender_ooxml_ref"
    }
    if len(referenced_ids) > 1:
        raise AppError(422, "multiple_ooxml_sources", "一个快照只能克隆一份主招标 DOCX 的 OOXML 块")
    for document_id in referenced_ids:
        tender = db.get(TenderDocument, document_id)
        if tender is None or tender.project_id != project.id:
            raise AppError(403, "invalid_ooxml_source", "OOXML 来源不属于当前项目")
    source_cache: dict[str, Any] = {}
    if referenced_ids:
        primary_id = next(iter(referenced_ids))
        primary = _source_document(db, primary_id, source_cache)
        facts["response_term"] = (
            "响应"
            if any("响应文件" in paragraph.text for paragraph in primary.paragraphs)
            else "投标"
        )
        document = docx.Document(
            str(
                FileStore().path_for(db.get(StoredFile, db.get(TenderDocument, primary_id).file_id))
            )
        )
    else:
        document = docx.Document()
    clear_body(document)
    if export_kind == "review":
        _review_watermark(document)
    _footer(document, snapshot.snapshot_no)
    _cover(document, project, snapshot, facts, export_kind, qa["stats"])
    node_map = {node["id"]: node for node in snapshot.tree_json}
    children_count: dict[str, int] = {}
    for node in snapshot.tree_json:
        if node["parent_id"]:
            children_count[node["parent_id"]] = children_count.get(node["parent_id"], 0) + 1
    omitted = {node["id"] for node in snapshot.tree_json if node.get("mapping_status") == "omitted"}
    cleanup: list[dict[str, Any]] = []
    ooxml_errors: list[str] = []
    first_top = True
    for node in snapshot.tree_json:
        ancestor = node
        skip = False
        while ancestor:
            if ancestor["id"] in omitted:
                skip = True
                break
            ancestor = node_map.get(ancestor.get("parent_id"))
        if skip:
            continue
        level = min(node["display_number"].count(".") + 1, 3)
        title = (
            node["title"]
            if re.match(r"^(?:\d+(?:\.\d+)*[\.、]|[一二三四五六七八九十]+、|第.+章)", node["title"])
            else f"{node['display_number']} {node['title']}"
        )
        _heading(document, title, level, page_break=level == 1 and not first_top)
        first_top = False
        revision = snapshot.selected_revisions_json.get(node["id"])
        if not revision:
            continue
        for block in revision["content_json"]:
            kind = block.get("type")
            if kind in {"paragraph", "placeholder"}:
                _text(document, str(block.get("text", "")), facts)
            elif kind == "heading":
                _heading(document, str(block.get("text", "")), min(level + 1, 3))
            elif kind == "list":
                for item in block.get("items", []):
                    _text(
                        document,
                        f"• {item}" if block.get("ordered") is not True else f"1. {item}",
                        facts,
                    )
            elif kind == "table":
                _render_table(document, block.get("rows", []), facts)
            elif kind == "fact_ref":
                value = snapshot.facts_json.get(block.get("fact_key"), {}).get("value")
                _text(
                    document,
                    str(value) if value not in (None, "") else f"[[{block.get('fact_key')}]]",
                    facts,
                )
            elif kind == "attachment_ref":
                _render_attachment(document, db, block)
            elif kind == "tender_ooxml_ref":
                _render_ooxml(
                    document,
                    db,
                    node,
                    block,
                    facts,
                    source_cache,
                    cleanup,
                    ooxml_errors,
                    bool(children_count.get(node["id"])),
                )
            else:
                raise AppError(422, "invalid_content_block", "快照包含不支持的内容块")
    if include_sources:
        _heading(document, "附录：素材来源与原文追溯", 1, True)
        for node in snapshot.tree_json:
            revision = snapshot.selected_revisions_json.get(node["id"])
            if not revision:
                continue
            source = (
                revision.get("source_asset_revision_id")
                or revision.get("source_history_revision_id")
                or revision["source_type"]
            )
            _text(document, f"{node['display_number']} {node['title']}：{source}", facts, 10)
            if node.get("source_anchor") and referenced_ids:
                anchor = db.scalar(
                    select(TenderBlock).where(
                        TenderBlock.document_id == next(iter(referenced_ids)),
                        TenderBlock.anchor_key == node["source_anchor"],
                    )
                )
                if anchor:
                    _text(document, f"原文锚点 {anchor.anchor_key}：{anchor.text[:500]}", facts, 9)
    output = io.BytesIO()
    document.save(output)
    data = output.getvalue()
    ooxml_errors = list(dict.fromkeys(ooxml_errors))
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            corrupt = archive.testzip()
            xml = archive.read("word/document.xml").decode("utf-8")
        reopened = docx.Document(io.BytesIO(data))
        if corrupt:
            ooxml_errors.append("zip_crc_error")
        output_placeholders = list(dict.fromkeys(PLACEHOLDER_RE.findall(xml)))
    except Exception as exc:
        raise AppError(502, "docx_validation_failed", "DOCX 重新打开校验失败") from exc
    result_qa = {
        **qa,
        "paragraphs": len(reopened.paragraphs),
        "tables": len(reopened.tables),
        "output_placeholders": output_placeholders,
        "placeholder_count": len(output_placeholders),
        "ooxml_errors": ooxml_errors,
        "ooxml_valid": not ooxml_errors,
        "cleanup": cleanup,
        "file_size": len(data),
    }
    return data, result_qa
