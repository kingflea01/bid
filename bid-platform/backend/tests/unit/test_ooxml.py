import io

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from app.services.export.ooxml import clear_body, clone_elements, table_signature
from app.services.structure.cleanup import clean_table


def test_ooxml_clone_preserves_table_grid_span_and_vmerge():
    source = Document()
    table = source.add_table(rows=2, cols=3)
    table.rows[0].cells[0].text = "序号"
    table.rows[0].cells[1].text = "价格"
    table.rows[0].cells[2].text = "分项名称"
    table.rows[1].cells[0].text = "1"
    table.rows[1].cells[1].text = "100"
    table.rows[1].cells[2].text = "服务"
    grid_span = OxmlElement("w:gridSpan")
    grid_span.set(qn("w:val"), "2")
    table.rows[1].cells[0]._tc.get_or_add_tcPr().append(grid_span)
    merge = OxmlElement("w:vMerge")
    merge.set(qn("w:val"), "restart")
    table.rows[0].cells[0]._tc.get_or_add_tcPr().append(merge)
    expected = table_signature(table._tbl)
    target = Document()
    clear_body(target)
    cloned = clone_elements(target, [table._tbl])[0]
    assert clean_table(cloned) == 1
    assert table_signature(cloned) == expected
    output = io.BytesIO()
    target.save(output)
    reopened = Document(io.BytesIO(output.getvalue()))
    assert table_signature(reopened.tables[0]._tbl) == expected
