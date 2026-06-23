#!/usr/bin/env python3
"""
步骤4 骨架完善脚手架
读取 skeleton.json + bid-extraction-result.json，识别目标章节，
检测去重冲突，输出增强提示供 Agent 参考。

Usage:
  python3 skeleton_enhance.py --skeleton <skeleton.json> --bid-info <bid-extraction-result.json>
"""

import json
import sys
import argparse

BIZ_CHAPTER_KEYWORDS = ["商务资料", "商务文件", "商务部分", "资质"]
TECH_CHAPTER_KEYWORDS = ["响应方案", "技术方案", "技术部分", "技术响应", "服务方案"]


def clean_text(text: str) -> str:
    return text.replace(" ", "").replace("，", "").replace("。", "").replace("\n", "").replace("\t", "")


def find_chapter(chapters: list, keywords: list) -> dict:
    for ch in chapters:
        title = ch.get("title", "")
        for kw in keywords:
            if kw in title:
                return ch
    return None


def check_duplicate(chapter: dict, target_text: str) -> bool:
    target_clean = clean_text(target_text)
    for el in chapter.get("elements", []):
        if el.get("type") == "paragraph":
            el_clean = clean_text(el.get("text", ""))
            if target_clean and len(target_clean) > 4:
                if target_clean in el_clean or el_clean in target_clean:
                    return True
    return False


def extract_merge_data(bid_info: dict) -> dict:
    quals = bid_info.get("qualifications", {})
    eval_criteria = bid_info.get("evaluationCriteria", {})
    tech_req = bid_info.get("technicalRequirements", {})
    disqualify = bid_info.get("disqualifyingFactors", [])

    biz_items = []
    tech_items = []

    if quals:
        if quals.get("qualificationRequirements") or quals.get("basicRequirements"):
            biz_items.append("资质要求")
        if quals.get("personnelRequirements"):
            biz_items.append("人员要求")
        if quals.get("performanceRequirements"):
            biz_items.append("业绩要求")
        if quals.get("financialRequirements"):
            biz_items.append("财务要求")

    if eval_criteria:
        if eval_criteria.get("method") or eval_criteria.get("items"):
            tech_items.append("评审方式")
        items = eval_criteria.get("items", [])
        if items:
            tech_items.append(f"评分项({len(items)}项)")

    if tech_req:
        func_reqs = tech_req.get("functionalRequirements", [])
        non_func = tech_req.get("nonFunctionalRequirements", [])
        if func_reqs:
            tech_items.append(f"功能需求({len(func_reqs)}项)")
        if non_func:
            tech_items.append(f"非功能需求({len(non_func)}项)")
        if tech_req.get("servicePeriod") or tech_req.get("qualityRequirements"):
            tech_items.append("服务要求")

    return {
        "biz_items": biz_items,
        "tech_items": tech_items,
        "disqualify_count": len(disqualify) if disqualify else 0,
        "qualifications": quals,
        "evaluationCriteria": eval_criteria,
        "technicalRequirements": tech_req,
        "disqualifyingFactors": disqualify,
    }


def generate_enhance_hints(skeleton: dict, bid_info: dict) -> dict:
    chapters = skeleton.get("chapters", [])
    biz_chapter = find_chapter(chapters, BIZ_CHAPTER_KEYWORDS)
    tech_chapter = find_chapter(chapters, TECH_CHAPTER_KEYWORDS)

    merge_data = extract_merge_data(bid_info)

    hints = {
        "biz_chapter_found": biz_chapter is not None,
        "biz_chapter_title": biz_chapter.get("title", "") if biz_chapter else None,
        "tech_chapter_found": tech_chapter is not None,
        "tech_chapter_title": tech_chapter.get("title", "") if tech_chapter else None,
        "biz_items": merge_data["biz_items"],
        "tech_items": merge_data["tech_items"],
        "disqualify_count": merge_data["disqualify_count"],
        "duplicates": [],
    }

    if biz_chapter:
        qual_data = merge_data["qualifications"]
        if qual_data.get("qualificationRequirements"):
            for req in qual_data["qualificationRequirements"]:
                if check_duplicate(biz_chapter, req):
                    hints["duplicates"].append({
                        "target": "商务资料",
                        "content": req[:40],
                        "reason": "资质要求内容已存在",
                    })
        if qual_data.get("personnelRequirements"):
            for req in qual_data["personnelRequirements"]:
                if check_duplicate(biz_chapter, req):
                    hints["duplicates"].append({
                        "target": "商务资料",
                        "content": req[:40],
                        "reason": "人员要求内容已存在",
                    })
        if qual_data.get("performanceRequirements"):
            for req in qual_data["performanceRequirements"]:
                if check_duplicate(biz_chapter, req):
                    hints["duplicates"].append({
                        "target": "商务资料",
                        "content": req[:40],
                        "reason": "业绩要求内容已存在",
                    })

    if tech_chapter:
        tech_data = merge_data["technicalRequirements"]
        func_reqs = tech_data.get("functionalRequirements", [])
        for req in func_reqs:
            if check_duplicate(tech_chapter, req):
                hints["duplicates"].append({
                    "target": "响应方案",
                    "content": req[:40],
                    "reason": "技术需求内容已存在",
                })

    return hints


def format_hints(hints: dict) -> str:
    lines = []

    lines.append("=== 增强提示 ===")

    if hints["biz_chapter_found"]:
        items = hints["biz_items"]
        if items:
            lines.append(f"[商务资料] 可合并：{', '.join(items)}")
        else:
            lines.append(f"[商务资料] 无可合并的资质数据")
    else:
        lines.append(f"[商务资料] ⚠️ 未找到商务资料章节，无法合并")

    if hints["tech_chapter_found"]:
        items = hints["tech_items"]
        if items:
            lines.append(f"[响应方案] 可合并：{', '.join(items)}")
        else:
            lines.append(f"[响应方案] 无可合并的评审/技术数据")
    else:
        lines.append(f"[响应方案] ⚠️ 未找到响应方案章节，无法合并")

    dq = hints["disqualify_count"]
    if dq > 0:
        lines.append(f"[编写指南] 废标因素 {dq} 项")

    if hints["duplicates"]:
        lines.append("")
        lines.append("=== 去重警告 ===")
        for d in hints["duplicates"]:
            lines.append(f"[{d['target']}] \"{d['content']}\" — {d['reason']}")
    else:
        lines.append("")
        lines.append("=== 去重检查: 无冲突 ===")

    lines.append("")
    lines.append("=== Agent 操作提示 ===")
    lines.append("1. 将资质要求合并到商务资料章节末尾（Heading 3 + Normal 段落）")
    lines.append("2. 将评审方式说明合并到响应方案章节末尾")
    lines.append("3. 将技术需求逐项合并到响应方案章节末尾")
    lines.append("4. 将服务与质量要求合并到响应方案章节末尾")
    lines.append("5. 废标因素写入 bid-writing-guide.json 的 disqualificationChecklist")
    lines.append("6. 去重检查：跳过已在目标章节中存在的内容")
    lines.append("7. 生成 bid-writing-guide.json（含 fillingPriorities, fillingInstructions, scoringGuide）")
    lines.append("8. 保存后运行 validate 命令检查结果")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="步骤4 骨架完善脚手架")
    parser.add_argument("--skeleton", "-s", required=True, help="skeleton.json 路径")
    parser.add_argument("--bid-info", "-b", required=True, help="bid-extraction-result.json 路径")
    args = parser.parse_args()

    try:
        with open(args.skeleton, "r", encoding="utf-8") as f:
            skeleton = json.load(f)
    except FileNotFoundError:
        print(f"Skeleton file not found: {args.skeleton}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in skeleton: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.bid_info, "r", encoding="utf-8") as f:
            bid_info = json.load(f)
    except FileNotFoundError:
        print(f"Bid info file not found: {args.bid_info}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in bid info: {e}", file=sys.stderr)
        sys.exit(1)

    hints = generate_enhance_hints(skeleton, bid_info)
    print(format_hints(hints))


if __name__ == "__main__":
    main()
