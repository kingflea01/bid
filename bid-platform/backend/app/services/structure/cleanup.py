import re
from typing import Any

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

INSTRUCTION_PATTERNS = [
    re.compile(pattern)
    for pattern in (
        r"^注\s*[：:]",
        r"^说明\s*[：:]",
        r"^备注\s*[：:]",
        r"本章格式仅供参考",
        r"格式仅供参考",
        r"^供应商\s*(应|须|还?可)",
        r"^请\s*供应商",
        r"^经会计师事务所",
        r"^近三年是指",
        r"^格式自拟",
        r"^响应方案应根据",
        r"^注明",
        r"^此处填写",
    )
]
ATTACH_PATTERN = re.compile(r"^(?:此处附|附)\s*[：:]\s*(.+)")
HEADER_KEYWORDS = (
    "序号",
    "分项名称",
    "价格",
    "税额",
    "价税",
    "计算过程",
    "偏差",
    "项目名称",
    "发包人",
    "姓名",
    "职称",
    "合同价格",
)


def paragraph_text(element) -> str:
    return "".join(node.text or "" for node in element.iter(qn("w:t"))).strip()


def set_paragraph_text(element, text: str) -> None:
    for child in list(element):
        if child.tag == qn("w:r"):
            element.remove(child)
    run = OxmlElement("w:r")
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    element.append(run)


def fill_fields(text: str, fields: dict[str, Any]) -> str:
    replacements = {
        "（项目名称）": "project_name",
        "(项目名称)": "project_name",
        "（项目编号）": "project_number",
        "(项目编号)": "project_number",
        "（采购人名称）": "purchaser",
        "（供应商名称）": "supplier_name",
        "（供应商全名）": "supplier_name",
        "(供应商全名)": "supplier_name",
        "（注册地址名称）": "registered_address",
        "(注册地址名称)": "registered_address",
        "（法定代表人姓名）": "legal_rep",
        "(法定代表人姓名)": "legal_rep",
    }
    for old, key in replacements.items():
        value = fields.get(key)
        if value:
            text = text.replace(old, str(value))
    text = re.sub(r"日期\s*[：:]\s*年\s*月\s*日", "日期：[[落款日期]]", text)
    return re.sub(r"年\s+月\s+日", "[[落款日期]]", text)


def clean_paragraph(element, fields: dict[str, Any]) -> tuple[str, str]:
    text = paragraph_text(element)
    if not text:
        return "empty", text
    attach = ATTACH_PATTERN.match(text)
    if attach:
        value = f"[[附件：{attach.group(1).strip().rstrip('。；;')}]]"
        set_paragraph_text(element, value)
        return "attach", value
    if any(pattern.search(text) for pattern in INSTRUCTION_PATTERNS):
        parent = element.getparent()
        if parent is not None:
            parent.remove(element)
        return "remove", text
    filled = fill_fields(text, fields)
    if filled != text:
        set_paragraph_text(element, filled)
        return "filled", filled
    return "keep", text


def clean_table(table_element) -> int:
    rows = table_element.findall(qn("w:tr"))
    header_count = 0
    for row in rows:
        cells = row.findall(qn("w:tc"))
        texts = [
            "".join(node.text or "" for node in cell.iter(qn("w:t"))).strip() for cell in cells
        ]
        if len(texts) < 3 or not any(
            any(keyword in text for keyword in HEADER_KEYWORDS) for text in texts
        ):
            break
        header_count += 1
    if not header_count:
        return 0
    for row in rows[header_count:]:
        for cell in row.findall(qn("w:tc")):
            paragraphs = cell.findall(qn("w:p"))
            for paragraph in paragraphs[1:]:
                cell.remove(paragraph)
            if paragraphs:
                for run in list(paragraphs[0]):
                    if run.tag == qn("w:r"):
                        paragraphs[0].remove(run)
    return len(rows) - header_count
