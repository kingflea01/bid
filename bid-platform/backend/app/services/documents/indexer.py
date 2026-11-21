import re
from datetime import date
from typing import Any

DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
TOTAL_RE = re.compile(r"(?:项目预算|预算金额|采购预算|最高限价)[：:\s]*([0-9,，]+(?:\.\d+)?)\s*元")
MASKS = ("----", "——", "详见附件", "待定", "（空）", "(空)", "留空", "XXXX")
METADATA_PATTERNS = {
    "project_name": r"项目名称[：:]\s*(.+?)(?:\s{2,}|\n|$)",
    "project_number": r"(?:项目编号|采购编号)[：:]\s*(.+?)(?:\s{2,}|\n|$)",
    "purchaser": r"采\s*购\s*人[：:]\s*(.+?)(?:\s{2,}|\n|$)",
    "agency": r"(?:代理机构|招标机构)[：:]\s*(.+?)(?:\s{2,}|\n|$)",
}


def extract_metadata(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, pattern in METADATA_PATTERNS.items():
        match = re.search(pattern, text)
        if match:
            result[key] = match.group(1).strip().lstrip("|").strip()
    match = TOTAL_RE.search(text)
    if match:
        result["budget"] = float(match.group(1).replace(",", "").replace("，", ""))
    return result


def _amount(value: str) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", value.replace(",", "").replace("，", ""))
    return float(match.group()) if match else None


def validate_tender_text(text: str) -> dict[str, Any]:
    lines = text.splitlines()
    checks: list[dict[str, Any]] = []

    def add(code: str, severity: str, message: str) -> None:
        checks.append({"code": code, "severity": severity, "message": message})

    package_rows: dict[int, tuple[str, float]] = {}
    for line in lines:
        cells = [cell.strip() for cell in line.split("|")]
        if len(cells) == 4 and cells[0].isdigit():
            amount = _amount(cells[3])
            if amount is not None:
                package_rows[int(cells[0])] = (cells[1], amount)
    if package_rows:
        numbers = sorted(package_rows)
        missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
        if missing:
            add("package_numbers", "warning", f"分包号不连续：{missing}")
        stated = extract_metadata(text).get("budget")
        if stated is not None:
            difference = sum(value[1] for value in package_rows.values()) - stated
            if abs(difference) >= 1:
                add("budget_total", "warning", f"分包预算合计与总预算相差 {difference:.2f} 元")
    else:
        add("package_table", "info", "未识别分包预算表，需人工核对")

    dates: list[tuple[date, date]] = []
    for line in lines:
        found = DATE_CN.findall(line)
        if "至" in line and len(found) >= 2:
            first = date(*(int(part) for part in found[0]))
            second = date(*(int(part) for part in found[1]))
            dates.append((first, second))
            if first > second:
                add("date_order", "warning", f"日期区间倒置：{first} 至 {second}")
    if not dates:
        add("dates", "info", "未识别明确日期区间")
    masked = [
        (index, mask) for index, line in enumerate(lines, 1) for mask in MASKS if mask in line
    ]
    if masked:
        add("masked_fields", "warning", f"发现 {len(masked)} 处空白、打码或附件待核字段")
    return {"checks": checks, "warning_count": sum(c["severity"] == "warning" for c in checks)}
