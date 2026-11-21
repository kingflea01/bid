from pathlib import Path
from typing import Any

import fitz
import pdfplumber

from app.core.errors import bad_request
from app.services.documents.anchors import pdf_line_anchor, pdf_table_anchor
from app.services.documents.docx_parser import (
    CHAPTER_RE,
    FORMAT_KEYWORDS,
    numbering_level,
    strip_numbering,
)
from app.services.documents.indexer import extract_metadata, validate_tender_text

PARSER_VERSION = "pdf-v1"


def _heading(block: dict[str, Any], median_size: float) -> int | None:
    text = block["text"].strip()
    if not text or len(text) > 45 or text.endswith(("。", "；", "：", "，")):
        return None
    numbered = numbering_level(text)
    size = block["style_json"].get("size_pt") or 0
    bold = block["style_json"].get("bold", False)
    if numbered and (bold or size >= median_size or numbered >= 2):
        return numbered
    if CHAPTER_RE.match(text) and len(text) <= 30:
        return 1
    if len(text) <= 35 and bold and size > median_size:
        return 1
    return None


def parse_pdf(path: Path) -> dict[str, Any]:
    try:
        document = fitz.open(path)
    except Exception as exc:
        raise bad_request("PDF 无法解析", code="invalid_pdf") from exc
    blocks: list[dict[str, Any]] = []
    scanned_pages: list[int] = []
    page_sizes: list[float] = []
    raw_pages: list[dict[str, Any]] = []
    with document:
        page_count = len(document)
        for page_index, page in enumerate(document):
            page_no = page_index + 1
            data = page.get_text("dict", sort=True)
            page_blocks = []
            for block_no, raw_block in enumerate(data.get("blocks", [])):
                if raw_block.get("type") != 0:
                    continue
                for line_no, line in enumerate(raw_block.get("lines", [])):
                    spans = line.get("spans", [])
                    text = "".join(span.get("text", "") for span in spans).strip()
                    if not text:
                        continue
                    sizes = [float(span.get("size", 0)) for span in spans]
                    size = max(sizes, default=0.0)
                    bold = any(
                        "bold" in span.get("font", "").lower() or int(span.get("flags", 0)) & 16
                        for span in spans
                    )
                    record = {
                        "anchor_key": pdf_line_anchor(page_no, block_no, line_no),
                        "block_type": "paragraph",
                        "order_no": 0,
                        "page_no": page_no,
                        "bbox_json": [
                            float(v) for v in line.get("bbox", raw_block.get("bbox", []))
                        ],
                        "text": text,
                        "style_json": {"size_pt": size, "bold": bold},
                    }
                    page_blocks.append(record)
                    page_sizes.append(size)
            if not page_blocks:
                scanned_pages.append(page_no)
            blocks.extend(page_blocks)
            raw_pages.append({"page_no": page_no, "blocks": page_blocks})
    for order, block in enumerate(blocks):
        block["order_no"] = order
    median = sorted(page_sizes)[len(page_sizes) // 2] if page_sizes else 0
    headings = [(block, _heading(block, median)) for block in blocks]
    chapters = [
        (block, level)
        for block, level in headings
        if level == 1 and CHAPTER_RE.match(block["text"])
    ]
    target = next(
        (block for block, _ in chapters if any(k in block["text"] for k in FORMAT_KEYWORDS)), None
    )
    outline = []
    format_chapter = None
    if target:
        later = [block for block, _ in chapters if block["order_no"] > target["order_no"]]
        end_order = later[0]["order_no"] if later else len(blocks)
        format_chapter = {
            "start_anchor": target["anchor_key"],
            "end_anchor": blocks[end_order]["anchor_key"] if end_order < len(blocks) else None,
            "text": target["text"],
        }
        selected = [
            (block, level)
            for block, level in headings
            if target["order_no"] < block["order_no"] < end_order and level
        ]
        previous = None
        for block, level in selected:
            key = (level, strip_numbering(block["text"]))
            if key == previous:
                continue
            outline.append(
                {
                    "title": block["text"],
                    "level": level,
                    "source_start_anchor": block["anchor_key"],
                    "confidence": 0.85 if block["style_json"].get("bold") else 0.65,
                    "paragraph_index": block["order_no"],
                }
            )
            previous = key
        for index, item in enumerate(outline):
            item["source_end_anchor"] = (
                outline[index + 1]["source_start_anchor"]
                if index + 1 < len(outline)
                else format_chapter["end_anchor"]
            )
    table_pages = [
        page["page_no"]
        for page in raw_pages
        if any(
            any(k in b["text"] for k in ("评分", "评审", *FORMAT_KEYWORDS)) for b in page["blocks"]
        )
    ]
    table_assist_error = False
    if table_pages:
        try:
            with pdfplumber.open(path) as pdf:
                for page_no in table_pages:
                    for table_no, table in enumerate(pdf.pages[page_no - 1].extract_tables()):
                        rows = [
                            [(cell or "").strip().replace("\n", " / ") for cell in row]
                            for row in table
                        ]
                        if not rows:
                            continue
                        text = "\n".join(
                            [
                                f"[TABLE {table_no + 1}]",
                                *(" | ".join(row) for row in rows),
                                "[/TABLE]",
                            ]
                        )
                        blocks.append(
                            {
                                "anchor_key": pdf_table_anchor(page_no, table_no),
                                "block_type": "table",
                                "order_no": len(blocks),
                                "page_no": page_no,
                                "text": text,
                                "style_json": {"rows": rows},
                            }
                        )
        except Exception:
            table_assist_error = True
    blocks.sort(key=lambda item: item["order_no"])
    text = "\n".join(block["text"] for block in blocks)
    qa = validate_tender_text(text)
    if table_assist_error:
        qa["checks"].append(
            {
                "code": "pdf_table_assist_failed",
                "severity": "warning",
                "message": "部分 PDF 表格无法可靠恢复，请人工核对",
            }
        )
        qa["warning_count"] += 1
    return {
        "blocks": blocks,
        "outline": outline,
        "text": text,
        "metadata": extract_metadata(text),
        "page_count": page_count,
        "scanned_pages": scanned_pages,
        "parser_version": PARSER_VERSION,
        "qa": {
            **validate_tender_text(text),
            "format_chapter": format_chapter,
            "ocr_performed": False,
            "table_assist_pages": table_pages,
        },
    }
