#!/usr/bin/env python3
"""Single entry point for tender extraction, structure merge and bid assembly."""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from builder.build import build_bid  # noqa: E402
from core.extract import build_index  # noqa: E402
from core.output_dir import create_output_dir  # noqa: E402
from core.structure import timed_build_structure  # noqa: E402


def resolve_input(root, name):
    candidate = Path(name).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (root / "input", root, Path.cwd()):
        path = base / name
        if path.exists():
            return path.resolve()
    return None


def resolve_template(root, name):
    if not name:
        return SKILL_DIR / "config" / "bid-templates" / "default.md"
    candidate = Path(name).expanduser()
    if candidate.is_absolute() and candidate.exists():
        return candidate
    for base in (root, SKILL_DIR, Path.cwd()):
        path = base / name
        if path.exists():
            return path.resolve()
    return None


def write_extract(index, output_dir):
    text = index.pop("text")
    (output_dir / "extracted.txt").write_text(text, encoding="utf-8")
    (output_dir / "tender.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def target_dir(root, args, metadata):
    if args.output_dir:
        path = Path(args.output_dir).expanduser()
        if not path.is_absolute():
            path = (root / path).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path
    return create_output_dir(
        root,
        args.org or metadata.get("purchaser", ""),
        args.project or metadata.get("project_name", ""),
        args.time,
    )


def prepare_project(args, root, tender_path, template_path):
    started = time.perf_counter()
    index = build_index(tender_path)
    output_dir = target_dir(root, args, index.get("metadata", {}))
    write_extract(index, output_dir)

    qa = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "core" / "validate_tables.py"),
            str(output_dir / "extracted.txt"),
        ],
        capture_output=True,
        text=True,
    )
    (output_dir / "qa.txt").write_text(qa.stdout, encoding="utf-8")

    structure = timed_build_structure(
        output_dir / "tender.json", template_path, args.package, output_dir
    )
    timing = dict(index.get("timing", {}))
    timing.update(structure.get("timing", {}))
    timing["total_ms"] = round((time.perf_counter() - started) * 1000, 2)
    (output_dir / "timing.json").write_text(
        json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {
        "output_dir": output_dir,
        "index": index,
        "structure": structure,
        "timing": timing,
    }


def print_structure(result):
    index = result["index"]
    structure = result["structure"]
    print(f"output: {result['output_dir']}")
    print(f"format_chapter: {(index.get('format_chapter') or {}).get('text', '未识别')}")
    print(f"outline_items: {len(index.get('outline', []))}")
    print(f"structure_stats: {json.dumps(structure.get('stats', {}), ensure_ascii=False)}")
    print(f"timing: {json.dumps(result['timing'], ensure_ascii=False)}")


def run_extract(args):
    root = Path(args.root).expanduser().resolve()
    tender_path = resolve_input(root, args.tender)
    if tender_path is None:
        raise SystemExit(f"未找到招标文件：{args.tender}")
    index = build_index(tender_path)
    output_dir = target_dir(root, args, index.get("metadata", {}))
    write_extract(index, output_dir)
    (output_dir / "timing.json").write_text(
        json.dumps(index.get("timing", {}), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"output: {output_dir}")
    print(f"outline_items: {len(index.get('outline', []))}")
    print(f"timing: {json.dumps(index.get('timing', {}), ensure_ascii=False)}")
    return 0


def run_structure(args):
    root = Path(args.root).expanduser().resolve()
    tender_path = resolve_input(root, args.tender)
    if tender_path is None:
        raise SystemExit(f"未找到招标文件：{args.tender}（已查找 input/ 与工作区根目录）")
    template_path = resolve_template(root, args.template)
    if template_path is None:
        raise SystemExit(f"未找到标书章节模板：{args.template}")

    result = prepare_project(args, root, tender_path, template_path)
    print_structure(result)
    return 0


def run_build(args):
    root = Path(args.root).expanduser().resolve()
    tender_path = resolve_input(root, args.tender)
    if tender_path is None:
        raise SystemExit(f"未找到招标文件：{args.tender}")

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser()
        if not output_dir.is_absolute():
            output_dir = (root / output_dir).resolve()
    else:
        output_dir = None

    need_prepare = (
        output_dir is None
        or not (output_dir / "structure.json").exists()
        or not (output_dir / "tender.json").exists()
        or not (output_dir / "extracted.txt").exists()
    )

    if need_prepare:
        template_path = resolve_template(root, args.template)
        if template_path is None:
            raise SystemExit(f"未找到标书章节模板：{args.template}")
        result = prepare_project(args, root, tender_path, template_path)
        output_dir = result["output_dir"]
        print_structure(result)
    else:
        output_dir.mkdir(parents=True, exist_ok=True)

    build_started = time.perf_counter()
    build_result = build_bid(
        output_dir,
        tender_path,
        SKILL_DIR,
        company_code=args.company,
        product_code=args.product,
    )
    elapsed = round((time.perf_counter() - build_started) * 1000, 2)
    build_result["build_ms"] = elapsed

    timing_path = output_dir / "timing.json"
    timing = {}
    if timing_path.exists():
        timing = json.loads(timing_path.read_text(encoding="utf-8"))
    timing["build_ms"] = elapsed
    timing_path.write_text(json.dumps(timing, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"bid: {build_result['bid']}")
    print(f"placeholders: {build_result['placeholders']}")
    print(f"cleanup: {build_result['cleanup']}")
    print(f"qa: {build_result['qa']}")
    print(f"tables: {build_result['tables']} | paragraphs: {build_result['paragraphs']}")
    print(f"placeholders_count: {build_result['placeholders_count']}")
    print(f"build_ms: {elapsed}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Tender bid workbench")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("--root", default=".", help="workspace root")
        p.add_argument("--tender", required=True, help="tender file name or path")
        p.add_argument("--output-dir", default=None, help="explicit output directory")
        p.add_argument("--org", default="", help="purchaser name for folder naming")
        p.add_argument("--project", default="", help="project name for folder naming")
        p.add_argument("--time", default=None, help="folder timestamp yyyymmdd-hhmm")

    p_extract = sub.add_parser("extract", help="extract text and tender index")
    common(p_extract)
    p_extract.set_defaults(func=run_extract)

    p_structure = sub.add_parser("structure", help="merge tender outline with user template")
    common(p_structure)
    p_structure.add_argument("--package", default="未指定")
    p_structure.add_argument("--company", default="C1")
    p_structure.add_argument("--product", default="P1")
    p_structure.add_argument(
        "--template",
        default="config/bid-templates/default.md",
        help="Markdown chapter template",
    )
    p_structure.set_defaults(func=run_structure)

    p_build = sub.add_parser("build", help="assemble bid.docx")
    common(p_build)
    p_build.add_argument("--package", default="未指定")
    p_build.add_argument("--company", default="C1")
    p_build.add_argument("--product", default="P1")
    p_build.add_argument(
        "--template", default="config/bid-templates/default.md"
    )
    p_build.set_defaults(func=run_build)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
