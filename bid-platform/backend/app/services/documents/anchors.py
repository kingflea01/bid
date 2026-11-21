from typing import Any


def docx_paragraph_anchor(index: int) -> str:
    return f"docx:p:{index:06d}"


def docx_table_anchor(index: int) -> str:
    return f"docx:tbl:{index:06d}"


def pdf_line_anchor(page_no: int, block_no: int, line_no: int) -> str:
    return f"pdf:p{page_no:04d}:b{block_no:03d}:l{line_no:02d}"


def pdf_table_anchor(page_no: int, table_no: int) -> str:
    return f"pdf:p{page_no:04d}:t{table_no:03d}"


def anchor_map(blocks: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {block["anchor_key"]: block for block in blocks}


def validate_anchor_quote(block: Any, quote: str) -> bool:
    normalized_quote = "".join(quote.split())
    text = block.get("text", "") if isinstance(block, dict) else block.text
    normalized_text = "".join(text.split())
    return bool(normalized_quote and normalized_quote in normalized_text)
