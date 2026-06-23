#!/usr/bin/env python3
"""
标书骨架提取 CLI 工具
提供六个子命令：
  parse            — 解析招标文件为结构化 JSON（含 plain_text + elements）
  extract-info     — 步骤2：关键信息提取脚手架（读取 plain_text，供 Agent 填充）
  skeleton-gen     — 步骤3：骨架提取脚手架（生成章节地图，供 Agent 填充）
  skeleton-enhance — 步骤4：骨架完善脚手架（生成增强提示，供 Agent 填充）
  validate         — 验证 skeleton.json 结构完整性
  template         — 从 skeleton.json 生成 Word 模板文件

Usage:
  python3 cli.py parse <file_path> [--output <path>]
  python3 cli.py extract-info <structured_content.json> --output <path>
  python3 cli.py skeleton-gen <structured_content.json> --output <path>
  python3 cli.py skeleton-enhance --skeleton <path> --bid-info <path> --output-dir <dir>
  python3 cli.py validate <skeleton.json>
  python3 cli.py template <skeleton.json 路径> [--output <path>]
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


def cmd_template(args):
    """从 skeleton.json 生成 Word 模板"""
    skeleton_path = Path(args.skeleton_path)

    if not skeleton_path.exists():
        print(f"Skeleton file not found: {skeleton_path}", file=sys.stderr)
        sys.exit(1)

    with open(skeleton_path, "r", encoding="utf-8") as f:
        try:
            skeleton = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {skeleton_path}: {e}", file=sys.stderr)
            sys.exit(1)

    # 验证骨架结构
    if not isinstance(skeleton, dict):
        print(f"Invalid skeleton.json: expected object, got {type(skeleton).__name__}", file=sys.stderr)
        sys.exit(1)

    chapters = skeleton.get("chapters")
    if chapters is None:
        print("Warning: skeleton.json missing 'chapters' field", file=sys.stderr)
    elif not isinstance(chapters, list):
        print(f"Invalid skeleton.json: 'chapters' must be a list", file=sys.stderr)
        sys.exit(1)
    elif len(chapters) == 0:
        print("Warning: skeleton.json has no chapters (0 chapters)", file=sys.stderr)

    # 导入 inject_placeholders 模块
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    try:
        from docx import Document
    except ImportError as e:
        print(f"Missing dependency: python-docx ({e})", file=sys.stderr)
        print("Install with: pip3 install python-docx", file=sys.stderr)
        sys.exit(1)

    # 复用 inject_placeholders 中的构建逻辑
    import inject_placeholders
    doc = inject_placeholders.build_docx(skeleton)

    # 输出路径
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = skeleton_path.parent / "template.docx"

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    doc.save(output_path)

    # 统计信息
    chapter_count = len(skeleton.get("chapters", []))
    placeholders = set()
    for ch in skeleton.get("chapters", []):
        placeholders.update(ch.get("placeholders", []))
    cover = skeleton.get("cover_template", {})
    placeholders.update(cover.get("placeholders", []))

    print(f"已保存到: {output_path}", file=sys.stderr)
    print(f"统计: 章节 {chapter_count} 个, 占位符 {len(placeholders)} 种", file=sys.stderr)
    print(f"占位符列表: {', '.join(sorted(placeholders))}", file=sys.stderr)


def cmd_extract_info(args):
    """步骤2：关键信息提取脚手架"""
    structured_path = Path(args.structured_content_path)

    if not structured_path.exists():
        print(f"File not found: {structured_path}", file=sys.stderr)
        sys.exit(1)

    with open(structured_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {structured_path}: {e}", file=sys.stderr)
            sys.exit(1)

    plain_text = data.get("plain_text", "")
    elements = data.get("elements", [])

    print("=== 文档概要 ===")
    print(f"文件: {data.get('source_file', 'unknown')}")
    print(f"类型: {data.get('file_type', 'unknown')}")
    print(f"纯文本长度: {len(plain_text)} 字符")
    print(f"结构化元素: {len(elements)} 个")

    h1_list = []
    for el in elements:
        if el.get("is_heading") and el.get("heading_level") == 1:
            h1_list.append(el.get("text", "").strip())

    if h1_list:
        print(f"\nH1 标题 ({len(h1_list)} 个):")
        for h in h1_list:
            print(f"  - {h}")

    print(f"\n=== Agent 操作提示 ===")
    print(f"1. 阅读 plain_text，按照 bid-info-extraction SKILL.md 的 JSON Schema 提取关键信息")
    print(f"2. 提取维度: meta, basicInfo, timeline, qualifications, technicalRequirements, "
          f"evaluationCriteria, contractTerms, disqualifyingFactors")
    print(f"3. 按照 bid-info-extraction 阶段2 进行风险规则匹配")
    print(f"4. 将结果保存到: {args.output}")
    print(f"5. 使用 json.dumps(data, ensure_ascii=False, indent=2) 保存")


def cmd_skeleton_gen(args):
    """步骤3：骨架提取脚手架"""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import skeleton_gen

    structured_path = Path(args.structured_content_path)

    if not structured_path.exists():
        print(f"File not found: {structured_path}", file=sys.stderr)
        sys.exit(1)

    with open(structured_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {structured_path}: {e}", file=sys.stderr)
            sys.exit(1)

    elements = data.get("elements", [])
    if not elements:
        print("错误: structured_content.json 的 elements 为空", file=sys.stderr)
        sys.exit(1)

    chapter_map = skeleton_gen.generate_chapter_map(elements)
    print(skeleton_gen.format_map(chapter_map))


def cmd_skeleton_enhance(args):
    """步骤4：骨架完善脚手架"""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import skeleton_enhance

    skeleton_path = Path(args.skeleton)
    bid_info_path = Path(args.bid_info)

    if not skeleton_path.exists():
        print(f"Skeleton file not found: {skeleton_path}", file=sys.stderr)
        sys.exit(1)
    if not bid_info_path.exists():
        print(f"Bid info file not found: {bid_info_path}", file=sys.stderr)
        sys.exit(1)

    with open(skeleton_path, "r", encoding="utf-8") as f:
        try:
            skeleton = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in skeleton: {e}", file=sys.stderr)
            sys.exit(1)

    with open(bid_info_path, "r", encoding="utf-8") as f:
        try:
            bid_info = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in bid info: {e}", file=sys.stderr)
            sys.exit(1)

    hints = skeleton_enhance.generate_enhance_hints(skeleton, bid_info)
    print(skeleton_enhance.format_hints(hints))


def cmd_validate(args):
    """验证 skeleton.json 结构"""
    sys.path.insert(0, str(SKILL_DIR / "scripts"))
    import validator

    skeleton_path = Path(args.skeleton_path)

    if not skeleton_path.exists():
        print(f"File not found: {skeleton_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(skeleton_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print("=== skeleton.json 验证报告 ===", file=sys.stderr)
        print(f"\u274c JSON 可解析 \u2014 {e}", file=sys.stderr)
        print("=== 结果: 未通过（1 致命）===", file=sys.stderr)
        sys.exit(1)

    results = validator.validate_skeleton(data)
    report = validator.format_report(results)
    print(report)

    has_issue = any(not r.passed and r.severity in (validator.Severity.FATAL, validator.Severity.ERROR) for r in results)
    sys.exit(1 if has_issue else 0)


def main():
    parser = argparse.ArgumentParser(
        description="标书骨架提取 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 解析招标文件（输出 JSON 到 stdout）
  python3 cli.py parse inputs/招标文件.docx

  # 解析并保存到文件
  python3 cli.py parse inputs/招标文件.docx --output output/structured_content.json

  # 步骤2：关键信息提取脚手架
  python3 cli.py extract-info output/structured_content.json --output output/bid-extraction-result.json

  # 步骤3：骨架提取脚手架
  python3 cli.py skeleton-gen output/structured_content.json --output output/skeleton.json

  # 验证 skeleton.json
  python3 cli.py validate output/skeleton.json

  # 步骤4：骨架完善脚手架
  python3 cli.py skeleton-enhance --skeleton output/skeleton.json --bid-info output/bid-extraction-result.json --output-dir output/

  # 从 skeleton.json 生成 Word 模板
  python3 cli.py template output/skeleton.json --output output/template.docx
"""
    )

    subparsers = parser.add_subparsers(dest="command", help="子命令")

    # parse 子命令
    parse_parser = subparsers.add_parser("parse", help="解析招标文件为结构化 JSON")
    parse_parser.add_argument("file_path", help="招标文件路径（支持 .docx/.pdf/.txt/.doc/.html/.png 等）")
    parse_parser.add_argument("--output", "-o", help="输出文件路径（默认输出到 stdout）")
    parse_parser.set_defaults(func=cmd_parse)

    # extract-info 子命令
    extract_parser = subparsers.add_parser("extract-info", help="步骤2：关键信息提取脚手架")
    extract_parser.add_argument("structured_content_path", help="structured_content.json 路径")
    extract_parser.add_argument("--output", "-o", required=True, help="输出 bid-extraction-result.json 路径")
    extract_parser.set_defaults(func=cmd_extract_info)

    # skeleton-gen 子命令
    gen_parser = subparsers.add_parser("skeleton-gen", help="步骤3：骨架提取脚手架（生成章节地图）")
    gen_parser.add_argument("structured_content_path", help="structured_content.json 路径")
    gen_parser.add_argument("--output", "-o", required=True, help="输出 skeleton.json 路径")
    gen_parser.set_defaults(func=cmd_skeleton_gen)

    # skeleton-enhance 子命令
    enhance_parser = subparsers.add_parser("skeleton-enhance", help="步骤4：骨架完善脚手架（生成增强提示）")
    enhance_parser.add_argument("--skeleton", "-s", required=True, help="skeleton.json 路径")
    enhance_parser.add_argument("--bid-info", "-b", required=True, help="bid-extraction-result.json 路径")
    enhance_parser.add_argument("--output-dir", "-o", required=True, help="输出目录")
    enhance_parser.set_defaults(func=cmd_skeleton_enhance)

    # validate 子命令
    validate_parser = subparsers.add_parser("validate", help="验证 skeleton.json 结构完整性")
    validate_parser.add_argument("skeleton_path", help="skeleton.json 路径")
    validate_parser.set_defaults(func=cmd_validate)

    # template 子命令
    template_parser = subparsers.add_parser("template", help="从 skeleton.json 生成 Word 模板")
    template_parser.add_argument("skeleton_path", help="skeleton.json 文件路径")
    template_parser.add_argument("--output", "-o", help="Word 模板输出路径（默认与 skeleton.json 同目录）")
    template_parser.set_defaults(func=cmd_template)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
