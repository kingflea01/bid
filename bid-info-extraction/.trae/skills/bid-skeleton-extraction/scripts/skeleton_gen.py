#!/usr/bin/env python3
"""
步骤3 骨架提取脚手架
读取 structured_content.json 的 elements，识别"响应文件格式"章节边界，
输出结构化的"章节地图"供 Agent 参考。

Usage:
  python3 skeleton_gen.py <structured_content.json>
"""

import json
import sys
import re

RESPONSE_FORMAT_KEYWORDS = [
    "响应文件格式",
    "投标文件格式",
    "响应文件组成",
]

CHAPTER_KEYWORDS = [
    "响应函", "投标函", "报价函",
    "授权委托书", "法定代表人身份证明",
    "响应保证金", "投标保证金",
    "报价表", "投标报价", "开标一览表",
    "商务资料", "商务文件", "商务部分",
    "响应方案", "技术方案", "技术部分", "技术响应",
]


def find_response_format_section(elements: list) -> tuple:
    """定位响应文件格式章节，返回 (start_idx, end_idx, h1_title)"""
    h1_indices = []
    for i, el in enumerate(elements):
        if el.get("is_heading") and el.get("heading_level") == 1:
            h1_indices.append(i)

    for idx in h1_indices:
        text = elements[idx].get("text", "")
        for kw in RESPONSE_FORMAT_KEYWORDS:
            if kw in text:
                next_h1 = len(elements)
                for h in h1_indices:
                    if h > idx:
                        next_h1 = h
                        break
                return idx, next_h1, text.strip()

    if h1_indices:
        last = h1_indices[-1]
        return last, len(elements), elements[last].get("text", "").strip()

    return None, None, None


def identify_chapter_boundaries(elements: list, start: int, end: int) -> list:
    """在响应文件格式章节内识别封面和子章节边界"""
    chapter_starts = []
    for i in range(start + 1, end):
        el = elements[i]
        text = el.get("text", "").strip()
        if el.get("type") != "paragraph" or el.get("is_heading"):
            continue
        match = re.match(r'^(\d+)\.\s*([^\d\s]+)', text)
        if not match:
            continue
        chapter_name = match.group(2)
        if len(text) < 30:
            for kw in CHAPTER_KEYWORDS:
                if kw in chapter_name:
                    chapter_starts.append(i)
                    break

    chapter_starts = sorted(list(set(chapter_starts)))
    return chapter_starts


def generate_chapter_map(elements: list) -> dict:
    """生成章节地图"""
    start_idx, end_idx, h1_title = find_response_format_section(elements)
    if start_idx is None:
        return {"error": "未找到响应文件格式章节", "all_h1": []}

    chapter_starts = identify_chapter_boundaries(elements, start_idx, end_idx)

    result = {
        "response_format_section": {
            "h1_title": h1_title,
            "start_idx": start_idx,
            "end_idx": end_idx,
            "total_elements": end_idx - start_idx,
        },
        "cover": {"range": None, "element_count": 0, "description": ""},
        "chapters": [],
        "h1_all": []
    }

    all_h1 = []
    for i, el in enumerate(elements):
        if el.get("is_heading") and el.get("heading_level") == 1:
            h1_text = el.get("text", "").strip()
            all_h1.append({"index": i, "text": h1_text})
            if i == start_idx:
                result["h1_all"].append({"index": i, "text": h1_text, "is_target": True})
            else:
                result["h1_all"].append({"index": i, "text": h1_text, "is_target": False})

    if not chapter_starts:
        result["error"] = "响应文件格式章节内未识别到子章节"
        return result

    first_chapter = chapter_starts[0]
    cover_start = start_idx + 1
    cover_end = first_chapter

    cover_elements = elements[cover_start:cover_end]
    cover_texts = [el.get("text", "") for el in cover_elements if el.get("type") == "paragraph"]

    result["cover"] = {
        "range": f"[{cover_start}, {cover_end})",
        "element_count": cover_end - cover_start,
        "description": " → ".join(t[:30] for t in cover_texts if t.strip()),
        "has_purchase_no": any("采购编号" in t or "项目编号" in t for t in cover_texts),
        "has_supplier": any("供应商" in t for t in cover_texts),
        "has_date": any("日" in t and "期" in t for t in cover_texts),
    }

    for ci, start in enumerate(chapter_starts):
        end = chapter_starts[ci + 1] if ci + 1 < len(chapter_starts) else end_idx
        title = elements[start].get("text", "").strip()
        ch_elements = elements[start:end]
        tables_count = sum(1 for el in ch_elements if el.get("type") == "table")

        result["chapters"].append({
            "index": ci + 1,
            "title": title,
            "range": f"[{start}, {end})",
            "element_count": end - start,
            "paragraph_count": sum(1 for el in ch_elements if el.get("type") == "paragraph"),
            "table_count": tables_count,
        })

    return result


def format_map(chapter_map: dict) -> str:
    if "error" in chapter_map:
        return f"错误: {chapter_map['error']}"

    lines = ["=== 招标文件 H1 章节列表 ==="]
    for h in chapter_map.get("h1_all", []):
        marker = " ← 目标章节（响应文件格式）" if h.get("is_target") else ""
        lines.append(f"  [{h['index']}] {h['text']}{marker}")

    rf = chapter_map["response_format_section"]
    lines.append("")
    lines.append(f"=== 响应文件格式章节结构 ===")
    lines.append(f"  标题: {rf['h1_title']}")
    lines.append(f"  范围: [{rf['start_idx']}, {rf['end_idx']}), 共 {rf['total_elements']} 个元素")

    cover = chapter_map["cover"]
    lines.append("")
    lines.append(f"  封面元素: {cover['range']} — {cover['element_count']} 个元素")
    if cover['description']:
        lines.append(f"    内容: {cover['description']}")
    lines.append(f"    特征: 采购编号={'✓' if cover['has_purchase_no'] else '✗'}, "
                 f"供应商={'✓' if cover['has_supplier'] else '✗'}, "
                 f"日期={'✓' if cover['has_date'] else '✗'}")

    lines.append("")
    lines.append("  子章节列表:")
    for ch in chapter_map["chapters"]:
        lines.append(f"    {ch['title']}")
        lines.append(f"      范围: {ch['range']}, {ch['element_count']} 个元素 "
                     f"(段落: {ch['paragraph_count']}, 表格: {ch['table_count']})")

    lines.append("")
    lines.append("=== Agent 操作提示 ===")
    lines.append("1. 封面元素: 将封面中的具体值替换为 {{SUPPLIER_NAME}}, {{PROJECT_NO}}, {{SIGN_DATE}} 等占位符")
    lines.append("2. 各子章节: 逐元素复制，按 SKILL.md 3.4 占位符规则替换 text 中的具体值")
    lines.append("3. 清理封面开头连续空行，各章节连续 3+ 空行缩减为 1 个")
    lines.append("4. 识别'数字.标题'模式（如 1.响应函、2.授权委托书）作为章节切分点")
    lines.append("5. 生成 skeleton.json 后运行 validate 命令检查结果")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 skeleton_gen.py <structured_content.json>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(1)

    elements = data.get("elements", [])
    if not elements:
        print("错误: structured_content.json 的 elements 为空", file=sys.stderr)
        sys.exit(1)

    chapter_map = generate_chapter_map(elements)
    print(format_map(chapter_map))


if __name__ == "__main__":
    main()
