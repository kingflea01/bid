import re
from typing import Any

from pydantic import BaseModel, ConfigDict

ALLOWED_BLOCK_TYPES = {
    "paragraph",
    "heading",
    "list",
    "table",
    "fact_ref",
    "attachment_ref",
    "placeholder",
    "tender_ooxml_ref",
}
FORBIDDEN_KEYS = re.compile(r"^(?:html|src|url|style|on[a-z]+)$", re.IGNORECASE)
UNSAFE_TEXT = re.compile(r"<\s*script|javascript\s*:", re.IGNORECASE)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class VersionedRequest(BaseModel):
    version: int | None = None
    project_version: int | None = None


def validate_blocks(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError("内容必须是块数组")
    for block in value:
        if not isinstance(block, dict) or block.get("type") not in ALLOWED_BLOCK_TYPES:
            raise ValueError("包含不支持的内容块")
        _validate_value(block)
        block_type = block["type"]
        if block_type == "fact_ref" and not block.get("fact_key"):
            raise ValueError("fact_ref 缺少 fact_key")
        if block_type == "attachment_ref" and not (
            block.get("file_id") or block.get("attachment_id")
        ):
            raise ValueError("attachment_ref 缺少 file_id 或 attachment_id")
        if block_type == "tender_ooxml_ref" and not block.get("anchor_key"):
            raise ValueError("tender_ooxml_ref 缺少 anchor_key")
    return value


def _validate_value(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if FORBIDDEN_KEYS.match(str(key)):
                raise ValueError(f"不允许的内容字段：{key}")
            _validate_value(child)
    elif isinstance(value, list):
        for child in value:
            _validate_value(child)
    elif isinstance(value, str) and UNSAFE_TEXT.search(value):
        raise ValueError("内容包含不安全文本")
