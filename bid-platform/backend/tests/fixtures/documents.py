import io

import fitz
from docx import Document
from docx.shared import Pt


def tender_docx_bytes() -> bytes:
    document = Document()
    document.add_paragraph("项目名称：示例服务项目")
    document.add_paragraph("项目编号：TENDER-001")
    document.add_paragraph("采购人：示例客户")
    document.add_heading("第五章 响应文件格式", level=1)
    for title in ("1. 响应函", "2. 技术方案"):
        paragraph = document.add_paragraph()
        run = paragraph.add_run(title)
        run.bold = True
        run.font.size = Pt(14)
        if title.startswith("1"):
            document.add_paragraph("注：供应商应按要求填写")
            document.add_paragraph("项目名称：（项目名称）")
            table = document.add_table(rows=2, cols=3)
            table.style = "Table Grid"
            for index, value in enumerate(("序号", "分项名称", "价格")):
                table.rows[0].cells[index].text = value
            for index, value in enumerate(("1", "示例服务", "100")):
                table.rows[1].cells[index].text = value
        else:
            document.add_paragraph("按实际方案填写")
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def text_pdf_bytes(with_scanned_page: bool = True) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), "Project Name: PDF Tender", fontsize=12)
    page.insert_text((72, 100), "Chapter 1 Response Requirements", fontsize=14)
    if with_scanned_page:
        document.new_page()
    pdf = document.tobytes()
    document.close()
    return pdf
