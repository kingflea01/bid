#!/usr/bin/env python3
"""
招标关键信息提取 CLI 工具
提供两个子命令：
  parse  — 解析招标文件为结构化 JSON（含 plain_text + elements）
  report — 将提取结果 JSON 注入 HTML 模板生成可视化报告

Usage:
  python3 cli.py parse <file_path>                    # 输出 JSON 到 stdout
  python3 cli.py report <json_path> [--output <path>] # 生成 HTML 报告
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Skill 根目录（基于此脚本位置计算，确保可移植性）
SKILL_DIR = Path(__file__).parent.parent


def cmd_parse(args):
    """解析招标文件为结构化 JSON"""
    filepath = args.file_path

    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    # 复用 extractor 模块
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import extractor

    ftype = extractor.detect_type(filepath)

    if ftype == "unknown":
        print(f"Cannot detect file type: {filepath}", file=sys.stderr)
        sys.exit(1)

    # 前置检查依赖
    required_imports = {
        "docx": ("pdf", "docx"),
        "fitz": ("pdf",),
    }
    for module, needed_by in required_imports.items():
        if ftype in needed_by:
            try:
                __import__(module)
            except ImportError:
                print(f"Missing dependency: {module} (required for {ftype} files)", file=sys.stderr)
                if module == "docx":
                    print("Install with: pip3 install python-docx", file=sys.stderr)
                elif module == "fitz":
                    print("Install with: pip3 install pymupdf", file=sys.stderr)
                sys.exit(1)

    try:
        extractors = {
            "pdf": extractor.extract_json_pdf,
            "docx": extractor.extract_json_docx,
            "txt": extractor.extract_json_txt,
        }

        if ftype not in extractors:
            # 降级：不支持结构化提取的格式，使用纯文本包装
            print(f"JSON extraction not supported for format: {ftype}, falling back to text.", file=sys.stderr)
            text_extractors = {
                "doc": extractor.extract_text_doc,
                "html": extractor.extract_text_html,
                "image": extractor.extract_text_image,
            }
            if ftype not in text_extractors:
                print(f"Unsupported file type: {ftype}", file=sys.stderr)
                sys.exit(1)
            text = text_extractors[ftype](filepath)
            if not text or not text.strip():
                print(f"Warning: extracted text is empty for {filepath}", file=sys.stderr)
            result = {
                "source_file": os.path.basename(filepath),
                "file_type": ftype,
                "plain_text": text,
                "elements": [{
                    "type": "paragraph",
                    "style": "Normal",
                    "text": text,
                    "is_heading": False,
                    "heading_level": None
                }]
            }
        else:
            elements = extractors[ftype](filepath)

            if not elements:
                print(f"Warning: no content extracted from {filepath} (0 elements)", file=sys.stderr)

            # 构建 plain_text
            plain_parts = []
            for elem in elements:
                if elem["type"] == "paragraph":
                    plain_parts.append(elem["text"])
                elif elem["type"] == "table":
                    for row in elem["rows"]:
                        plain_parts.append(" | ".join(row))
            plain_text = "\n".join(plain_parts)

            result = {
                "source_file": os.path.basename(filepath),
                "file_type": ftype,
                "plain_text": plain_text,
                "elements": elements
            }

        output = json.dumps(result, ensure_ascii=False, indent=2)
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"Output written to: {args.output}", file=sys.stderr)
        else:
            print(output)

    except Exception as e:
        print(f"Extraction failed: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_report(args):
    """将提取结果 JSON 注入 HTML 模板生成报告"""
    json_path = args.json_path

    if not os.path.isfile(json_path):
        print(f"JSON file not found: {json_path}", file=sys.stderr)
        sys.exit(1)

    # 读取 JSON 数据
    with open(json_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {json_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # 读取 HTML 模板
    template_path = SKILL_DIR / "assets" / "report-template.html"
    if not template_path.exists():
        print(f"Report template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    # 注入数据：替换 window.__BID_DATA__ = {...};
    json_str = json.dumps(data, ensure_ascii=False)
    injection = f"window.__BID_DATA__ = {json_str};"

    # 查找注入点：匹配 window.__BID_DATA__ = {...}; 模式
    import re
    pattern = r"window\.__BID_DATA__\s*=\s*\{.*?\};"
    match = re.search(pattern, template, re.DOTALL)
    if match:
        html = template[:match.start()] + injection + template[match.end():]
    else:
        # 如果模板中没有找到注入点，在 </head> 前注入
        injection_script = f"<script>\n{injection}\n</script>\n"
        html = template.replace("</head>", injection_script + "</head>")

    # 输出
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Report written to: {args.output}", file=sys.stderr)
    else:
        print(html)


def main():
    parser = argparse.ArgumentParser(
        description="招标关键信息提取 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 解析招标文件（输出 JSON 到 stdout）
  python3 cli.py parse inputs/招标文件.docx

  # 解析并保存到文件
  python3 cli.py parse inputs/招标文件.docx --output output/structured_content.json

  # 生成 HTML 报告
  python3 cli.py report output/bid-extraction-result.json --output output/report.html
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # parse 子命令
    parse_parser = subparsers.add_parser("parse", help="解析招标文件为结构化 JSON")
    parse_parser.add_argument("file_path", help="招标文件路径（支持 .docx/.pdf/.txt/.doc/.html/.png 等）")
    parse_parser.add_argument("--output", "-o", help="输出文件路径（默认输出到 stdout）")
    parse_parser.set_defaults(func=cmd_parse)

    # report 子命令
    report_parser = subparsers.add_parser("report", help="将提取结果 JSON 生成 HTML 报告")
    report_parser.add_argument("json_path", help="bid-extraction-result.json 文件路径")
    report_parser.add_argument("--output", "-o", help="HTML 报告输出路径（默认输出到 stdout）")
    report_parser.set_defaults(func=cmd_report)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
