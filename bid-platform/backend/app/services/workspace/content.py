import copy
import re
from collections.abc import Iterator
from typing import Any

PLACEHOLDER_RE = re.compile(r"\[\[(.+?)\]\]")


def normalize_block_aliases(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = copy.deepcopy(blocks)
    for block in result:
        if block.get("type") == "attachment_ref":
            if not block.get("file_id"):
                block["file_id"] = block.get("attachment_id")
            if not block.get("name"):
                block["name"] = block.get("label")
        elif block.get("type") == "placeholder":
            label = block.get("name") or block.get("label")
            if label:
                block["name"] = label
                block.setdefault("text", f"[[{label}]]")
    return result


def iter_values(value: Any) -> Iterator[Any]:
    if isinstance(value, dict):
        for child in value.values():
            yield from iter_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_values(child)
    else:
        yield value


def placeholders(blocks: list[dict[str, Any]]) -> list[str]:
    found = []
    for value in iter_values(blocks):
        if isinstance(value, str):
            found.extend(PLACEHOLDER_RE.findall(value))
    for block in blocks:
        if block.get("type") == "placeholder":
            name = block.get("name") or block.get("label") or block.get("text")
            if name and name not in found:
                found.append(str(name))
    return list(dict.fromkeys(found))


def fact_keys(blocks: list[dict[str, Any]]) -> set[str]:
    return {
        block["fact_key"]
        for block in blocks
        if block.get("type") == "fact_ref" and block.get("fact_key")
    }


def block_text(block: dict[str, Any]) -> str:
    kind = block.get("type")
    if kind in {"paragraph", "heading"}:
        return str(block.get("text", ""))
    if kind == "placeholder":
        return str(block.get("text") or f"[[{block.get('label') or block.get('name', '')}]]")
    if kind == "list":
        return "\n".join(str(item) for item in block.get("items", []))
    if kind == "table":
        return "\n".join(" | ".join(str(cell) for cell in row) for row in block.get("rows", []))
    if kind == "fact_ref":
        return f"[[{block.get('fact_key')}]]"
    if kind == "attachment_ref":
        label = (
            block.get("label")
            or block.get("name")
            or block.get("file_id")
            or block.get("attachment_id")
        )
        return f"[[附件：{label}]]"
    if kind == "tender_ooxml_ref":
        return f"[[按招标文件格式填写：{block.get('anchor_key')}]]"
    return ""
