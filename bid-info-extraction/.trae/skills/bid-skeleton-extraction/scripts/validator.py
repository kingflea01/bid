#!/usr/bin/env python3
"""
skeleton.json 结构验证器
验证封面结构、章节结构、占位符有效性等

Usage:
  python3 validator.py <skeleton.json>
"""

import json
import sys
import re
from dataclasses import dataclass, field
from enum import Enum


class Severity(Enum):
    FATAL = "FATAL"
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class ValidationResult:
    check_name: str
    passed: bool
    severity: Severity
    message: str = ""


ILLEGAL_CHAPTER_KEYWORDS = [
    "邀请书", "投标邀请", "采购邀请",
    "供应商须知", "投标须知",
    "合同草案", "合同条款", "合同格式",
    "工程量清单", "图纸",
    "技术标准", "技术规范",
]

ILLEGAL_PLACEHOLDERS = [
    "{{填写说明}}", "{{说明}}", "{{备注}}",
]

VALID_PLACEHOLDER_PATTERN = re.compile(r'\{\{[A-Z_]+(_\w+)?\}\}')


def validate_skeleton(data: dict) -> list[ValidationResult]:
    results = []

    if not isinstance(data, dict):
        results.append(ValidationResult("顶层结构", False, Severity.FATAL, f"预期 object，实际 {type(data).__name__}"))
        return results
    results.append(ValidationResult("顶层结构", True, Severity.INFO, "object"))

    # --- 封面检查 ---
    cover = data.get("cover_template")
    if cover is None:
        results.append(ValidationResult("cover_template 存在", False, Severity.FATAL, "缺少 cover_template 字段"))
    elif not isinstance(cover, dict):
        results.append(ValidationResult("cover_template 存在", False, Severity.FATAL, f"预期 object，实际 {type(cover).__name__}"))
    else:
        results.append(ValidationResult("cover_template 存在", True, Severity.INFO, ""))

        cover_elements = cover.get("elements", [])
        if not cover_elements:
            results.append(ValidationResult("cover_template.elements 非空", False, Severity.ERROR, "封面元素为空"))
        else:
            results.append(ValidationResult("cover_template.elements 非空", True, Severity.INFO, f"{len(cover_elements)} 个元素"))

            cover_text = " ".join(el.get("text", "") for el in cover_elements if el.get("type") == "paragraph")

            if "{{SUPPLIER_NAME}}" in cover_text:
                results.append(ValidationResult("封面含 SUPPLIER_NAME", True, Severity.INFO, ""))
            else:
                results.append(ValidationResult("封面含 SUPPLIER_NAME", False, Severity.ERROR, "封面未包含 {{SUPPLIER_NAME}} 占位符"))

            if "{{PROJECT_NO}}" in cover_text:
                results.append(ValidationResult("封面含 PROJECT_NO", True, Severity.INFO, ""))
            else:
                results.append(ValidationResult("封面含 PROJECT_NO", False, Severity.ERROR, "封面未包含 {{PROJECT_NO}} 占位符"))

            if "{{SIGN_DATE}}" in cover_text:
                results.append(ValidationResult("封面含 SIGN_DATE", True, Severity.INFO, ""))
            else:
                results.append(ValidationResult("封面含 SIGN_DATE", False, Severity.ERROR, "封面未包含 {{SIGN_DATE}} 占位符"))

            if "{{PROJECT_NAME}}" in cover_text:
                results.append(ValidationResult("封面含 PROJECT_NAME", True, Severity.INFO, ""))
            else:
                results.append(ValidationResult("封面含 PROJECT_NAME", False, Severity.WARNING, "封面未包含 {{PROJECT_NAME}}（部分招标文件封面不需要）"))

            if "{{BUYER_NAME}}" in cover_text:
                results.append(ValidationResult("封面含 BUYER_NAME", True, Severity.INFO, ""))
            else:
                results.append(ValidationResult("封面含 BUYER_NAME", False, Severity.WARNING, "封面未包含 {{BUYER_NAME}}（部分招标文件封面不需要）"))

            # 封面首行检查
            first_text = ""
            for el in cover_elements:
                if el.get("type") == "paragraph" and el.get("text", "").strip():
                    first_text = el["text"]
                    break
            if "{{SUPPLIER_NAME}}" in first_text:
                results.append(ValidationResult("封面首行为 SUPPLIER_NAME", True, Severity.INFO, ""))
            elif "{{PROJECT_NAME}}" in first_text:
                results.append(ValidationResult("封面首行为 SUPPLIER_NAME", False, Severity.ERROR, "封面首行是 {{PROJECT_NAME}}，应为 {{SUPPLIER_NAME}}"))
            else:
                results.append(ValidationResult("封面首行为 SUPPLIER_NAME", False, Severity.WARNING, f"封面首行不是占位符: \"{first_text[:30]}\""))

            # 封面空行检查
            empty_count = 0
            max_empty = 0
            for el in cover_elements:
                if el.get("type") == "paragraph" and el.get("text", "") == "":
                    empty_count += 1
                    max_empty = max(max_empty, empty_count)
                else:
                    empty_count = 0
            if max_empty > 2:
                results.append(ValidationResult("封面连续空行", False, Severity.WARNING, f"封面存在连续 {max_empty} 个空行"))

    # --- 章节检查 ---
    chapters = data.get("chapters")
    if chapters is None:
        results.append(ValidationResult("chapters 存在", False, Severity.FATAL, "缺少 chapters 字段"))
    elif not isinstance(chapters, list):
        results.append(ValidationResult("chapters 存在", False, Severity.FATAL, f"预期 list，实际 {type(chapters).__name__}"))
    elif len(chapters) < 2:
        results.append(ValidationResult("章节数 >= 2", False, Severity.ERROR, f"章节数: {len(chapters)}（应 >= 2）"))
    else:
        results.append(ValidationResult("章节数 >= 2", True, Severity.INFO, f"{len(chapters)} 个章节"))

        all_placeholders = set(cover.get("placeholders", []))
        all_chapter_text = ""

        for ci, ch in enumerate(chapters):
            title = ch.get("title", "")
            elements = ch.get("elements", [])
            all_chapter_text += " " + " ".join(el.get("text", "") for el in elements if el.get("type") == "paragraph")

            if not title:
                results.append(ValidationResult(f"章节{ci+1}标题", False, Severity.FATAL, "缺少 title"))
            else:
                for kw in ILLEGAL_CHAPTER_KEYWORDS:
                    if kw in title:
                        results.append(ValidationResult("章节标题合理性", False, Severity.WARNING, f"章节 \"{title}\" 包含疑似招标文件目录关键词: \"{kw}\""))
                        break

            if not elements:
                results.append(ValidationResult(f"章节{ci+1}元素", False, Severity.ERROR, f"\"{title}\" 无元素"))

            chapter_placeholders = ch.get("placeholders", [])
            if not isinstance(chapter_placeholders, list):
                results.append(ValidationResult(f"章节{ci+1}占位符", False, Severity.ERROR, f"placeholders 应为 list"))
            else:
                all_placeholders.update(chapter_placeholders)
                for p in chapter_placeholders:
                    if not VALID_PLACEHOLDER_PATTERN.match(p):
                        results.append(ValidationResult("占位符格式", False, Severity.WARNING, f"\"{title}\" 中 \"{p}\" 格式异常"))

            table_ok = True
            for ei, el in enumerate(elements):
                if el.get("type") == "table":
                    rows = el.get("rows", [])
                    if not rows:
                        results.append(ValidationResult(f"章节{ci+1}表格", False, Severity.ERROR, f"\"{title}\" 第{ei}个表格无行数据"))
                        table_ok = False

                required_fields = ["type"]
                if el.get("type") == "paragraph":
                    required_fields = ["type", "text", "is_heading", "heading_level"]
                elif el.get("type") == "table":
                    required_fields = ["type", "rows"]
                for f in required_fields:
                    if f not in el:
                        results.append(ValidationResult("元素结构", False, Severity.ERROR, f"\"{title}\" 第{ei}个元素缺少字段 \"{f}\""))

        for p in all_placeholders:
            if p in ILLEGAL_PLACEHOLDERS:
                results.append(ValidationResult("无效占位符", False, Severity.WARNING, f"占位符列表含 \"{p}\""))

        full_text = all_chapter_text
        empty_lines = re.findall(r'\n\s*\n\s*\n', full_text)
        if len(empty_lines) > 3:
            results.append(ValidationResult("连续空行", False, Severity.WARNING, f"发现 {len(empty_lines)} 处连续 3+ 空行"))
        else:
            results.append(ValidationResult("连续空行", True, Severity.INFO, ""))

        for p in ILLEGAL_PLACEHOLDERS:
            if p in full_text:
                results.append(ValidationResult("无效占位符(文本)", False, Severity.WARNING, f"章节文本含无效占位符 \"{p}\""))

    return results


def format_report(results: list[ValidationResult]) -> str:
    lines = ["=== skeleton.json 验证报告 ==="]
    fatals = 0
    errors = 0
    warnings = 0

    for r in results:
        icon = "✅" if r.passed else "❌"
        if r.severity == Severity.WARNING:
            icon = "⚠️"
        detail = f" — {r.message}" if r.message else ""
        lines.append(f"{icon} {r.check_name}{detail}")

        if not r.passed:
            if r.severity == Severity.FATAL:
                fatals += 1
            elif r.severity == Severity.ERROR:
                errors += 1
            elif r.severity == Severity.WARNING:
                warnings += 1

    total_issues = fatals + errors + warnings
    if total_issues == 0:
        lines.append("=== 结果: 通过 ===")
    else:
        parts = []
        if fatals:
            parts.append(f"{fatals} 致命")
        if errors:
            parts.append(f"{errors} 错误")
        if warnings:
            parts.append(f"{warnings} 警告")
        lines.append(f"=== 结果: 未通过（{', '.join(parts)}）===")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 validator.py <skeleton.json>", file=sys.stderr)
        sys.exit(1)

    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"=== skeleton.json 验证报告 ===")
        print(f"❌ JSON 可解析 — {e}")
        print(f"=== 结果: 未通过（1 致命）===")
        sys.exit(1)

    results = validate_skeleton(data)
    report = format_report(results)
    print(report)

    has_issue = any(not r.passed and r.severity in (Severity.FATAL, Severity.ERROR) for r in results)
    sys.exit(1 if has_issue else 0)


if __name__ == "__main__":
    main()
