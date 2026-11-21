import re
import zipfile
from pathlib import Path
from typing import Any

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

from app.core.config import get_settings
from app.core.errors import bad_request
from app.services.documents.anchors import docx_paragraph_anchor, docx_table_anchor
from app.services.documents.indexer import extract_metadata, validate_tender_text

PARSER_VERSION = "docx-v1"
CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百]+章")
FORMAT_KEYWORDS = ("响应文件格式", "响应文件编制", "响应文件组成", "投标文件格式", "投标文件编制")


def iter_blocks(document):
    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            yield Paragraph(child, document)
        elif child.tag == qn("w:tbl"):
            yield Table(child, document)


def font_size_pt(paragraph: Paragraph) -> float | None:
    for run in paragraph.runs:
        if run.font.size is not None:
            return run.font.size.pt
    try:
        if paragraph.style.font.size is not None:
            return paragraph.style.font.size.pt
    except (AttributeError, KeyError):
        pass
    return None


def bold_ratio(paragraph: Paragraph) -> float:
    runs = [run for run in paragraph.runs if run.text.strip()]
    return sum(1 for run in runs if run.bold) / len(runs) if runs else 0.0


def outline_level(paragraph: Paragraph) -> int | None:
    p_pr = paragraph._p.pPr
    node = p_pr.find(qn("w:outlineLvl")) if p_pr is not None else None
    if node is None:
        return None
    try:
        return int(node.get(qn("w:val")))
    except (TypeError, ValueError):
        return None


def is_toc_entry(paragraph: Paragraph) -> bool:
    text = paragraph.text.strip()
    style = (paragraph.style.name if paragraph.style else "").lower()
    return (
        text.endswith("页码")
        or (("toc" in style or "目录" in style) and bool(re.search(r"\d+\s*$", text)))
        or bool(re.search(r"\t\s*\d+\s*$", text))
    )


def numbering_level(text: str) -> int | None:
    patterns = (
        (r"^\d+\.\d+\.\d+", 3),
        (r"^\d+\.\d+", 2),
        (r"^\d+[\.、]", 1),
        (r"^[一二三四五六七八九十]+、", 1),
        (r"^（[一二三四五六七八九十]+）", 2),
    )
    for pattern, level in patterns:
        if re.match(pattern, text):
            return level
    return None


def strip_numbering(text: str) -> str:
    value = re.sub(r"^\d+(\.\d+)*[\.、]?\s*", "", text)
    value = re.sub(r"^[一二三四五六七八九十]+、\s*", "", value)
    return re.sub(r"[；。：，、]+$", "", value).strip()


def is_heading(paragraph: Paragraph) -> bool:
    text = paragraph.text.strip()
    if not text or is_toc_entry(paragraph):
        return False
    style = paragraph.style.name if paragraph.style else ""
    styled = "Heading" in style or "标题" in style or outline_level(paragraph) is not None
    numbered = numbering_level(text)
    if numbered is not None:
        if len(text) > 45 or text.endswith(("。", "：")):
            return False
        return (
            styled
            or bold_ratio(paragraph) >= 0.8
            or (font_size_pt(paragraph) or 0) >= 14
            or numbered >= 2
            or len(text) <= 45
        )
    if len(text) > 40 or text.endswith(("。", "；", "：", "，", "）")):
        return False
    return styled or (bold_ratio(paragraph) >= 0.8 and (font_size_pt(paragraph) or 0) >= 14)


def level_for(paragraph: Paragraph) -> int:
    text = paragraph.text.strip()
    numbered = numbering_level(text)
    if numbered:
        return numbered
    style = paragraph.style.name if paragraph.style else ""
    for level in (1, 2, 3):
        if f"Heading {level}" in style or style == f"标题 {level}":
            return level
    explicit = outline_level(paragraph)
    return (
        explicit + 1 if explicit is not None else (1 if (font_size_pt(paragraph) or 0) >= 14 else 2)
    )


def _table_data(table: Table, index: int) -> tuple[str, dict[str, Any]]:
    lines = [f"[TABLE {index + 1}]"]
    rows = []
    for row in table.rows:
        cells = []
        previous = None
        for cell in row.cells:
            if cell._tc is previous:
                continue
            previous = cell._tc
            cells.append(cell.text.strip().replace("\n", " / "))
        rows.append(cells)
        lines.append(" | ".join(cells))
    lines.append("[/TABLE]")
    tbl = table._tbl
    grid = tbl.findall(".//" + qn("w:tblGrid") + "/" + qn("w:gridCol"))
    style = {
        "rows": rows,
        "row_count": len(tbl.findall(qn("w:tr"))),
        "grid_cols": len(grid),
        "grid_widths": [col.get(qn("w:w")) for col in grid],
        "grid_span": len(tbl.findall(".//" + qn("w:gridSpan"))),
        "v_merge": len(tbl.findall(".//" + qn("w:vMerge"))),
    }
    return "\n".join(lines), style


def _validate_archive(path: Path) -> None:
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if (
                len(infos) > 5000
                or sum(info.file_size for info in infos)
                > get_settings().max_docx_uncompressed_bytes
            ):
                raise bad_request("DOCX 解压后大小或条目数超限", code="docx_bomb_rejected")
            if "word/document.xml" not in archive.namelist() or archive.testzip() is not None:
                raise bad_request("DOCX 包结构损坏", code="invalid_docx")
    except zipfile.BadZipFile as exc:
        raise bad_request("DOCX ZIP 结构无效", code="invalid_docx") from exc


def parse_docx(path: Path) -> dict[str, Any]:
    _validate_archive(path)
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise bad_request("DOCX 无法解析", code="invalid_docx") from exc
    paragraph_objects = {id(p._p): (index, p) for index, p in enumerate(document.paragraphs)}
    table_objects = {id(t._tbl): (index, t) for index, t in enumerate(document.tables)}
    blocks: list[dict[str, Any]] = []
    text_parts: list[str] = []
    for order, child in enumerate(document.element.body.iterchildren()):
        if id(child) in paragraph_objects:
            index, paragraph = paragraph_objects[id(child)]
            text = paragraph.text.strip()
            if not text:
                continue
            style = paragraph.style.name if paragraph.style else ""
            blocks.append(
                {
                    "anchor_key": docx_paragraph_anchor(index),
                    "block_type": "paragraph",
                    "order_no": order,
                    "paragraph_index": index,
                    "text": text,
                    "ooxml_path": f"/w:document/w:body/*[{order}]",
                    "style_json": {
                        "style": style,
                        "bold": round(bold_ratio(paragraph), 2),
                        "size_pt": font_size_pt(paragraph),
                        "outline_level": outline_level(paragraph),
                    },
                }
            )
            text_parts.append(text)
        elif id(child) in table_objects:
            index, table = table_objects[id(child)]
            text, style = _table_data(table, index)
            blocks.append(
                {
                    "anchor_key": docx_table_anchor(index),
                    "block_type": "table",
                    "order_no": order,
                    "table_index": index,
                    "text": text,
                    "ooxml_path": f"/w:document/w:body/*[{order}]",
                    "style_json": style,
                }
            )
            text_parts.append(text)
    by_paragraph = {
        block["paragraph_index"]: block for block in blocks if block["block_type"] == "paragraph"
    }
    chapters = [
        (index, p.text.strip())
        for index, p in enumerate(document.paragraphs)
        if CHAPTER_RE.match(p.text.strip())
        and not is_toc_entry(p)
        and len(p.text.strip()) <= 30
        and not p.text.strip().endswith(("；", "。", "，", "："))
    ]
    target = next(
        ((index, title) for index, title in chapters if any(k in title for k in FORMAT_KEYWORDS)),
        None,
    )
    outline: list[dict[str, Any]] = []
    format_chapter = None
    if target:
        start, title = target
        end = next((index for index, _ in chapters if index > start), len(document.paragraphs))
        format_chapter = {"index": start, "end": end, "text": title}
        candidates = [
            (index, p)
            for index, p in enumerate(document.paragraphs)
            if start < index < end and is_heading(p)
        ]
        previous = None
        for index, paragraph in candidates:
            title_key = strip_numbering(paragraph.text)
            level = level_for(paragraph)
            if previous == (level, title_key):
                continue
            outline.append(
                {
                    "paragraph_index": index,
                    "title": paragraph.text.strip(),
                    "level": level,
                    "confidence": 1.0
                    if bold_ratio(paragraph) >= 0.8 or outline_level(paragraph) is not None
                    else 0.7,
                }
            )
            previous = (level, title_key)
        for position, item in enumerate(outline):
            next_index = (
                outline[position + 1]["paragraph_index"] if position + 1 < len(outline) else end
            )
            item["source_start_anchor"] = by_paragraph.get(item["paragraph_index"], {}).get(
                "anchor_key"
            )
            item["source_end_anchor"] = by_paragraph.get(next_index, {}).get("anchor_key")
    text = "\n".join(text_parts)
    return {
        "blocks": blocks,
        "outline": outline,
        "text": text,
        "metadata": extract_metadata(text),
        "page_count": None,
        "scanned_pages": [],
        "parser_version": PARSER_VERSION,
        "qa": {
            **validate_tender_text(text),
            "format_chapter": format_chapter,
            "chapters": [{"index": i, "text": t} for i, t in chapters],
            "table_count": len(document.tables),
        },
    }
