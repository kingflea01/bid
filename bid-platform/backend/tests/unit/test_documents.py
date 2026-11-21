from app.services.documents.docx_parser import parse_docx
from app.services.documents.pdf_parser import parse_pdf
from app.services.structure.merge import merge_trees, tender_tree
from app.services.workspace.diff import structured_diff
from tests.fixtures.documents import tender_docx_bytes, text_pdf_bytes


def test_docx_outline_anchors_and_table_index(tmp_path):
    path = tmp_path / "tender.docx"
    path.write_bytes(tender_docx_bytes())
    result = parse_docx(path)
    assert [item["title"] for item in result["outline"]] == ["1. 响应函", "2. 技术方案"]
    assert result["metadata"]["project_number"] == "TENDER-001"
    assert result["qa"]["table_count"] == 1
    table = next(block for block in result["blocks"] if block["block_type"] == "table")
    assert table["style_json"]["grid_cols"] == 3
    assert all(item["source_start_anchor"] for item in result["outline"])


def test_text_pdf_has_page_anchors_and_marks_scanned_page(tmp_path):
    path = tmp_path / "tender.pdf"
    path.write_bytes(text_pdf_bytes())
    result = parse_pdf(path)
    assert result["page_count"] == 2
    assert result["scanned_pages"] == [2]
    assert result["qa"]["ocr_performed"] is False
    assert result["blocks"][0]["anchor_key"].startswith("pdf:p0001:")
    assert result["blocks"][0]["bbox_json"]


def test_deterministic_merge_and_structured_diff():
    outline = [
        {"title": "1. 投标函", "level": 1, "source_start_anchor": "a", "source_end_anchor": None}
    ]
    merged = merge_trees(
        tender_tree(outline), [{"title": "响应函", "content_lines": ["固定内容"], "children": []}]
    )
    assert len(merged["nodes"]) == 1
    assert merged["nodes"][0]["source"] == "tender"
    assert merged["nodes"][0]["children"][0]["source"] == "user_supplement"
    assert merged["nodes"][0]["children"][0]["content_json"][0]["text"] == "固定内容"
    diff = structured_diff(
        [{"type": "paragraph", "text": "旧"}], [{"type": "paragraph", "text": "新"}]
    )
    assert diff["changed"] is True
    assert diff["operations"][0]["op"] == "replace"
