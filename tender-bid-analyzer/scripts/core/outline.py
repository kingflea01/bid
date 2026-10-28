"""Tender outline extraction.

The two sample tenders use almost no Word heading styles; headings are manual
numbering on Normal paragraphs. The heuristics below combine numbering depth,
bold ratio, font size and TOC filtering.
"""

import re

from docx.oxml.ns import qn

CHAPTER_RE = re.compile(r"^第[一二三四五六七八九十百]+章")

FORMAT_KEYWORDS = [
    "响应文件格式",
    "响应文件编制",
    "响应文件组成",
    "投标文件格式",
    "投标文件编制",
    "响应文件编制要求",
]

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def text_of(paragraph):
    return paragraph.text.strip()


def font_size_pt(paragraph):
    for run in paragraph.runs:
        if run.font.size is not None:
            return run.font.size.pt
    try:
        if paragraph.style.font.size is not None:
            return paragraph.style.font.size.pt
    except Exception:
        pass
    return None


def bold_ratio(paragraph):
    runs = [r for r in paragraph.runs if r.text.strip()]
    if not runs:
        return 0.0
    return sum(1 for r in runs if r.bold) / len(runs)


def outline_level(paragraph):
    p_pr = paragraph._p.pPr
    if p_pr is None:
        return None
    node = p_pr.find(W_NS + "outlineLvl")
    if node is None:
        return None
    try:
        return int(node.get(W_NS + "val"))
    except (TypeError, ValueError):
        return None


def is_toc_entry(paragraph):
    text = text_of(paragraph)
    if text.endswith("页码"):
        return True
    style = (paragraph.style.name if paragraph.style else "").lower()
    if ("toc" in style or "目录" in style) and re.search(
        r"\t\s*(\d+|页码)\s*$", text
    ):
        return True
    return bool(re.search(r"\t\s*\d+\s*$", text))


def numbering_level(text):
    if re.match(r"^\d+\.\d+\.\d+", text):
        return 3
    if re.match(r"^\d+\.\d+", text):
        return 2
    if re.match(r"^\d+[\.、]", text):
        return 1
    if re.match(r"^[一二三四五六七八九十]+、", text):
        return 1
    if re.match(r"^（[一二三四五六七八九十]+）", text):
        return 2
    return None


def is_heading_candidate(paragraph):
    text = text_of(paragraph)
    if not text or is_toc_entry(paragraph):
        return False

    style = paragraph.style.name if paragraph.style else ""
    is_style_heading = (
        "Heading" in style or "标题" in style or outline_level(paragraph) is not None
    )
    numbered = numbering_level(text)

    if numbered is not None:
        if len(text) > 45:
            return False
        if is_style_heading:
            return True
        if bold_ratio(paragraph) >= 0.8:
            return True
        if (font_size_pt(paragraph) or 0) >= 14:
            return True
        if numbered >= 2 and len(text) <= 30:
            return True
        if text.endswith(("。", "：")):
            return False
        return True

    if len(text) > 40 or text.endswith(("。", "；", "：", "，", "）")):
        return False
    if is_style_heading:
        return True
    return bold_ratio(paragraph) >= 0.8 and (font_size_pt(paragraph) or 0) >= 14


def level_for(paragraph):
    text = text_of(paragraph)
    numbered = numbering_level(text)
    if numbered is not None:
        return numbered
    style = paragraph.style.name if paragraph.style else ""
    if "Heading 1" in style or style == "标题 1":
        return 1
    if "Heading 2" in style or style == "标题 2":
        return 2
    if "Heading 3" in style or style == "标题 3":
        return 3
    ol = outline_level(paragraph)
    if ol is not None:
        return ol + 1
    return 1 if (font_size_pt(paragraph) or 0) >= 14 else 2


def strip_numbering(text):
    stripped = re.sub(r"^\d+(\.\d+)*[\.、]?\s*", "", text)
    stripped = re.sub(r"^[一二三四五六七八九十]+、\s*", "", stripped)
    return re.sub(r"[；。：，、]+$", "", stripped).strip()


def list_body_chapters(document):
    chapters = []
    for index, paragraph in enumerate(document.paragraphs):
        text = text_of(paragraph)
        if not CHAPTER_RE.match(text):
            continue
        if is_toc_entry(paragraph):
            continue
        if text.endswith(("；", "。", "，", "：")) or len(text) > 30:
            continue
        chapters.append((index, text))
    return chapters


def find_format_chapter(chapters):
    for index, text in chapters:
        if any(keyword in text for keyword in FORMAT_KEYWORDS):
            return index, text
    return None


def extract_tender_outline(document):
    paragraphs = document.paragraphs
    chapters = list_body_chapters(document)
    target = find_format_chapter(chapters)

    if target is None:
        return {
            "chapters": [{"index": i, "text": t} for i, t in chapters],
            "format_chapter": None,
            "outline": [],
        }

    start, title = target
    end = len(paragraphs)
    for index, _ in chapters:
        if index > start:
            end = index
            break

    outline_start = start + 1
    for index in range(start + 1, end):
        text = text_of(paragraphs[index])
        if is_toc_entry(paragraphs[index]):
            continue
        if re.match(r"^(\d+[\.、]|[一二三四五六七八九十]+、)", text):
            outline_start = index
            break

    outline = []
    child_mode = False
    last_top_number = None
    previous_level = None
    previous_title = None

    for index in range(outline_start, end):
        paragraph = paragraphs[index]
        text = text_of(paragraph)
        if not is_heading_candidate(paragraph):
            continue

        numbered = numbering_level(text)
        top_match = re.match(r"^(\d+)[\.、]", text)
        level = level_for(paragraph)

        if top_match and numbered == 1:
            number = int(top_match.group(1))
            if child_mode:
                level = 2
            elif (
                number == 1
                and last_top_number is not None
                and last_top_number >= 2
                and previous_level == 1
            ):
                child_mode = True
                level = 2
            else:
                level = 1
                last_top_number = number
        elif numbered in (2, 3):
            child_mode = False
            level = numbered

        title_key = strip_numbering(text)
        if previous_level == level and previous_title == title_key:
            continue

        outline.append(
            {
                "index": index,
                "level": level,
                "text": text,
                "style": paragraph.style.name if paragraph.style else "",
                "bold": round(bold_ratio(paragraph), 2),
                "size_pt": font_size_pt(paragraph),
            }
        )
        previous_level = level
        previous_title = title_key

    return {
        "chapters": [{"index": i, "text": t} for i, t in chapters],
        "format_chapter": {"index": start, "text": title, "end": end},
        "outline": outline,
    }
