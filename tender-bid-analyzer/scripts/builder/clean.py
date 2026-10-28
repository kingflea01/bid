"""Cleaning and field filling for cloned tender blocks."""

import re

from docx.oxml import OxmlElement
from docx.oxml.ns import qn

INSTRUCTION_PATTERNS = [
    re.compile(r"^注\s*[：:]"),
    re.compile(r"^说明\s*[：:]"),
    re.compile(r"^备注\s*[：:]"),
    re.compile(r"本章格式仅供参考"),
    re.compile(r"格式仅供参考"),
    re.compile(r"^供应商\s*(应|须|还?可)"),
    re.compile(r"^请\s*供应商"),
    re.compile(r"^\(?\d+\)?[、.]?\s*供应商\s*(应|须)"),
    re.compile(r"^经会计师事务所"),
    re.compile(r"^近三年是指"),
    re.compile(r"^格式自拟"),
    re.compile(r"^响应方案应根据"),
    re.compile(r"^\d+\.\d+\.?\d*\s*供应商应"),
    re.compile(r"^注明"),
    re.compile(r"^\d+[、.]\s*本表"),
    re.compile(r"^\d+[、.]\s*大小写"),
    re.compile(r"^\d+[、.]\s*供应商要"),
    re.compile(r"^此处填写"),
]

ATTACH_PATTERN = re.compile(r"^(?:此处附|附)\s*[：:]\s*(.+)")
ATTACH_REPLACEMENTS = [
    (re.compile(r"^法人或者其他组织"), "[[附件：营业执照]]"),
    (re.compile(r"^（经审计的"), "[[附件：财务状况报告]]"),
    (re.compile(r"^提供企业"), "[[附件：纳税与社保证明]]"),
    (re.compile(r"^提供具备"), "[[附件：设备与人员证明]]"),
    (re.compile(r"^1[\.、]\s*信用中国"), "[[附件：信用中国查询截图]]"),
    (re.compile(r"^2[\.、]\s*中国政府采购网"), "[[附件：中国政府采购网查询截图]]"),
]
HEADER_KEYWORDS = [
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
]


def paragraph_text(element):
    return "".join(node.text or "" for node in element.iter(qn("w:t"))).strip()


def set_paragraph_text(element, text):
    for child in list(element):
        if child.tag == qn("w:r"):
            element.remove(child)
    run = OxmlElement("w:r")
    node = OxmlElement("w:t")
    node.set(qn("xml:space"), "preserve")
    node.text = text
    run.append(node)
    element.append(run)


def fill_fields(text, fields):
    replacements = {
        "（项目名称）": fields.get("project_name", ""),
        "（项目编号）": fields.get("project_number", ""),
        "(项目编号)": fields.get("project_number", ""),
        "(项目名称)": fields.get("project_name", ""),
        "（采购人名称）": fields.get("purchaser", ""),
        "（供应商名称）": fields.get("supplier_name", ""),
        "（供应商全名）": fields.get("supplier_name", ""),
        "(供应商全名)": fields.get("supplier_name", ""),
        "（注册地址名称）": fields.get("registered_address", ""),
        "(注册地址名称)": fields.get("registered_address", ""),
        "（法定代表人姓名）": fields.get("legal_rep", ""),
        "(法定代表人姓名）": fields.get("legal_rep", ""),
        "(法定代表人姓名)": fields.get("legal_rep", ""),
        "（单位名称）": "[[被授权人所在单位]]",
        "（被授权人的姓名）": fields.get("authorized_person", "[[被授权人姓名]]"),
        "（姓名及电话）": fields.get(
            "authorized_person_contact", "[[被授权人姓名及电话]]"
        ),
    }
    for old, new in replacements.items():
        if new:
            text = text.replace(old, new)

    project = fields.get("project_name", "")
    number = fields.get("project_number", "")
    if project or number:
        text = text.replace("（项目名称、项目编号）", f"{project}、{number}")

    text = text.replace(
        "法定代表人（签字或盖章）：",
        "法定代表人（签字或盖章）：[[法定代表人签字]]",
    )
    text = text.replace(
        "被授权人（签字或盖章）：",
        "被授权人（签字或盖章）：[[授权代表签字]]",
    )
    text = text.replace(
        "供应商代表（签字或盖章）：",
        "供应商代表（签字或盖章）：[[授权代表签字]]",
    )
    if fields.get("project_number"):
        text = re.sub(
            r"项目编号\s*[：:]\s*$",
            f"项目编号：{fields['project_number']}",
            text,
        )
    if fields.get("supplier_name"):
        text = re.sub(
            r"供应商\s*[：:]\s*供应商名称",
            f"供应商：{fields['supplier_name']}",
            text,
        )
        text = re.sub(
            r"供应商名称\s*[：:]\s*$",
            f"供应商名称：{fields['supplier_name']}",
            text,
        )
    text = re.sub(r"日期\s*[：:]\s*年\s*月\s*日", "日期：[[落款日期]]", text)
    text = re.sub(r"日期\s*[：:]\s*$", "日期：[[落款日期]]", text)
    text = re.sub(r"年\s+月\s+日", "[[落款日期]]", text)
    return text


def fill_content_placeholders(text, fields):
    mapping = {
        "公司名称": fields.get("supplier_name", ""),
        "统一社会信用代码": fields.get("credit_code", ""),
        "法定代表人": fields.get("legal_rep", ""),
        "注册地址": fields.get("registered_address", ""),
        "成立时间": fields.get("established", ""),
        "注册资本": fields.get("capital", ""),
        "主营业务": fields.get("main_business", ""),
        "资质证书": fields.get("qualifications", ""),
    }
    for key, value in mapping.items():
        if value:
            text = text.replace(f"[[{key}]]", value.strip().rstrip("。；;"))
    return text


def clean_paragraph(element, fields):
    text = paragraph_text(element)
    if not text:
        return "empty", None

    attach = ATTACH_PATTERN.match(text)
    if attach:
        name = attach.group(1).strip().rstrip("。；;")
        new_text = f"[[附件：{name}]]"
        set_paragraph_text(element, new_text)
        return "attach", new_text

    for pattern, replacement in ATTACH_REPLACEMENTS:
        if pattern.search(text):
            set_paragraph_text(element, replacement)
            return "attach", replacement

    for pattern in INSTRUCTION_PATTERNS:
        if pattern.search(text):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            return "remove", text

    filled = fill_fields(text, fields)
    if filled != text:
        set_paragraph_text(element, filled)
        return "filled", filled
    return "keep", text


def _cell_texts(row):
    result = []
    for cell in row.findall(qn("w:tc")):
        result.append(
            "".join(node.text or "" for node in cell.iter(qn("w:t"))).strip()
        )
    return result


def _header_row_count(rows):
    count = 0
    for row in rows:
        texts = _cell_texts(row)
        if len(texts) < 3:
            break
        hits = sum(
            1
            for text in texts
            if any(keyword in text for keyword in HEADER_KEYWORDS)
        )
        if hits == 0:
            break
        count += 1
    return count


def _clear_row(row):
    for cell in row.findall(qn("w:tc")):
        paragraphs = cell.findall(qn("w:p"))
        for paragraph in paragraphs[1:]:
            cell.remove(paragraph)
        if paragraphs:
            for run in list(paragraphs[0]):
                if run.tag == qn("w:r"):
                    paragraphs[0].remove(run)


def clean_table(table_element):
    rows = table_element.findall(qn("w:tr"))
    header_rows = _header_row_count(rows)
    if header_rows == 0:
        return 0
    cleared = 0
    for row in rows[header_rows:]:
        _clear_row(row)
        cleared += 1
    return cleared
