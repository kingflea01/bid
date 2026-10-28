#!/usr/bin/env python3
"""Run deterministic quality checks on text extracted from a tender document.

Usage:
    python3 validate_tables.py extracted.txt
    python3 validate_tables.py extracted.txt --stated-total 5499474
"""

import argparse
import re
import sys
from pathlib import Path

DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
TOTAL_PATTERNS = [
    re.compile(r"(?:项目预算|预算金额|采购预算|最高限价)[：:\s]*([0-9,，]+(?:\.\d+)?)\s*元"),
]
MASK_PATTERNS = ["----", "——", "详见附件", "待定", "（空）", "(空)", "留空", "XXXX"]
TABLE_START = re.compile(r"^\[TABLE(?:\s+\d+)?\]$")


def parse_tables(text):
    tables = []
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if TABLE_START.match(stripped):
            current = []
            continue
        if stripped == "[/TABLE]":
            if current is not None:
                tables.append(current)
            current = None
            continue
        if current is not None and stripped:
            current.append([cell.strip() for cell in stripped.split("|")])
    return tables


def parse_amount(value):
    cleaned = value.replace(",", "").replace("，", "").strip()
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    return float(match.group(1)) if match else None


def find_package_table(tables):
    best = None
    best_rows = {}
    for table in tables:
        rows = {}
        for cells in table:
            if len(cells) != 4 or not cells[0].isdigit():
                continue
            amount = parse_amount(cells[3])
            if amount is None:
                continue
            rows[int(cells[0])] = (cells[1], amount)
        if len(rows) > len(best_rows):
            best = table
            best_rows = rows
    return best, best_rows


def find_stated_total(text):
    for pattern in TOTAL_PATTERNS:
        match = pattern.search(text)
        if match:
            return parse_amount(match.group(1))
    return None


def find_label_date(lines, label, window=3):
    for index, line in enumerate(lines):
        if label not in line:
            continue
        for offset in range(window + 1):
            pos = index + offset
            if pos >= len(lines):
                break
            match = DATE_CN.search(lines[pos])
            if match:
                return tuple(int(part) for part in match.groups())
    return None


def check_dates(lines):
    messages = []

    for line in lines:
        dates = DATE_CN.findall(line)
        if "至" in line and len(dates) >= 2:
            first = tuple(int(part) for part in dates[0])
            second = tuple(int(part) for part in dates[1])
            if first <= second:
                messages.append(f"[PASS] date range ordered: {first} -> {second}")
            else:
                messages.append(f"[WARN] date range reversed: {first} -> {second}")
            break

    acquisition = find_label_date(lines, "获取")
    submission = find_label_date(lines, "递交截止")
    opening = find_label_date(lines, "开启")

    if acquisition:
        messages.append(f"[INFO] acquisition date: {acquisition}")
    else:
        messages.append("[WARN] acquisition date not found")

    if submission and opening:
        if submission <= opening:
            messages.append(f"[PASS] submission {submission} <= opening {opening}")
        else:
            messages.append(f"[WARN] submission {submission} > opening {opening}")
    else:
        messages.append("[WARN] submission or opening date not found")

    return messages


def check_masked(text):
    hits = []
    for number, line in enumerate(text.splitlines(), 1):
        for pattern in MASK_PATTERNS:
            if pattern in line:
                hits.append((number, pattern, line.strip()[:120]))
                break
    return hits


def check_names(tables, package_rows):
    for table in tables:
        rows = {}
        for cells in table:
            if len(cells) >= 5 and cells[0].isdigit():
                rows[int(cells[0])] = cells[1]
        if len(rows) < 5:
            continue
        diffs = [
            (number, package_rows[number][0], name)
            for number, name in rows.items()
            if number in package_rows and package_rows[number][0] != name
        ]
        if diffs:
            return diffs
    return []


def main():
    parser = argparse.ArgumentParser(description="Validate extracted tender tables")
    parser.add_argument("input", help="extracted text file")
    parser.add_argument("--stated-total", type=float, default=None)
    args = parser.parse_args()

    path = Path(args.input)
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 2

    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    tables = parse_tables(text)
    _, package_rows = find_package_table(tables)

    print("== Tender QA ==")
    print(f"tables: {len(tables)}")

    if not package_rows:
        print("[WARN] package table not detected; check manually")
    else:
        numbers = sorted(package_rows)
        expected = list(range(numbers[0], numbers[-1] + 1))
        missing = [number for number in expected if number not in package_rows]
        if missing:
            print(f"[WARN] package numbers not continuous; missing: {missing}")
        else:
            print(f"[PASS] package rows continuous: {numbers[0]}-{numbers[-1]}")

        total = sum(amount for _, amount in package_rows.values())
        print(f"[INFO] package budget sum: {total:,.0f}")
        stated = args.stated_total or find_stated_total(text)
        if stated is None:
            print("[WARN] stated total budget not found")
        else:
            diff = total - stated
            if abs(diff) < 1:
                print(f"[PASS] package sum matches stated total: {stated:,.0f}")
            else:
                print(
                    f"[WARN] package sum differs from stated total by {diff:,.0f} "
                    f"(sum {total:,.0f} vs stated {stated:,.0f})"
                )

        diffs = check_names(tables, package_rows)
        if diffs:
            print(f"[WARN] package names differ across sections: {len(diffs)}")
            for number, first, second in diffs[:5]:
                print(f"       package {number}: {first} / {second}")
        else:
            print("[PASS] package names consistent across detected tables")

    for message in check_dates(lines):
        print(message)

    masked = check_masked(text)
    if masked:
        print(f"[WARN] blank or masked fields: {len(masked)}")
        for number, pattern, snippet in masked[:8]:
            print(f"       line {number} [{pattern}] {snippet}")
    else:
        print("[PASS] no blank or masked fields detected")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
