#!/usr/bin/env python3
"""Create the per-project output folder with a deterministic name.

Usage:
    python3 make_output_dir.py --org "某大学" --project "图书馆数据库采购"
    python3 make_output_dir.py --org "某大学" --project "图书馆数据库采购" --time 20241127-0900
"""

import argparse
import re
from datetime import datetime
from pathlib import Path

INVALID = re.compile(r'[/\\:*?"<>|\s]+')
MULTI_HYPHEN = re.compile(r"-{2,}")


def sanitize(value, fallback):
    cleaned = INVALID.sub("-", value.strip())
    cleaned = MULTI_HYPHEN.sub("-", cleaned).strip("-")
    cleaned = cleaned[:40].strip("-")
    return cleaned or fallback


def unique_path(base):
    if not base.exists():
        return base
    index = 2
    while True:
        candidate = base.with_name(f"{base.name}-{index}")
        if not candidate.exists():
            return candidate
        index += 1


def create_output_dir(root, org, project, stamp=None):
    root = Path(root).expanduser().resolve()
    output_root = root / "output"
    output_root.mkdir(parents=True, exist_ok=True)
    if stamp is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M")
    else:
        stamp = stamp.strip()
    if not re.fullmatch(r"\d{8}-\d{4}", stamp):
        raise ValueError(f"invalid timestamp {stamp!r}; expected yyyymmdd-hhmm")
    org_name = sanitize(org, "未知招标单位")
    project_name = sanitize(project, "未命名项目")
    folder = unique_path(output_root / f"{stamp}-{org_name}-{project_name}")
    folder.mkdir(parents=True)
    return folder


def main():
    parser = argparse.ArgumentParser(description="Create a project output folder")
    parser.add_argument("--root", default=".", help="workspace root, default current directory")
    parser.add_argument("--org", default="", help="tender issuer name")
    parser.add_argument("--project", default="", help="project name")
    parser.add_argument("--time", default=None, help="timestamp yyyymmdd-hhmm, default now")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    output_root = root / "output"
    output_root.mkdir(parents=True, exist_ok=True)

    stamp = args.time or datetime.now().strftime("%Y%m%d-%H%M")
    if not re.fullmatch(r"\d{8}-\d{4}", stamp):
        print(f"ERROR: invalid --time {stamp!r}; expected yyyymmdd-hhmm")
        return 2

    org = sanitize(args.org, "未知招标单位")
    project = sanitize(args.project, "未命名项目")
    folder = unique_path(output_root / f"{stamp}-{org}-{project}")
    folder.mkdir(parents=True)

    print(folder)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
