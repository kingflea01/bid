import copy
from typing import Any

from docx.oxml.ns import qn


def clear_body(document) -> None:
    body = document.element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def block_elements(document, start_index: int | None, end_index: int | None):
    if start_index is None:
        return []
    body = document.element.body
    paragraph_positions = {
        body.index(paragraph._p): index for index, paragraph in enumerate(document.paragraphs)
    }
    table_positions = {body.index(table._tbl): index for index, table in enumerate(document.tables)}
    items = []
    for position, child in enumerate(body.iterchildren()):
        if position in paragraph_positions:
            items.append(("p", paragraph_positions[position], child))
        elif position in table_positions:
            items.append(("tbl", table_positions[position], child))
    start = next(
        (index for index, item in enumerate(items) if item[0] == "p" and item[1] == start_index),
        None,
    )
    if start is None:
        return []
    result = []
    for kind, index, element in items[start + 1 :]:
        if kind == "p" and end_index is not None and index == end_index:
            break
        result.append(element)
    return result


def clone_elements(target_document, elements):
    body = target_document.element.body
    section = body.find(qn("w:sectPr"))
    cloned = []
    for element in elements:
        new_element = copy.deepcopy(element)
        if section is not None:
            section.addprevious(new_element)
        else:
            body.append(new_element)
        cloned.append(new_element)
    return cloned


def table_signature(element) -> dict[str, Any]:
    return {
        "rows": len(element.findall(qn("w:tr"))),
        "grid_widths": [
            col.get(qn("w:w"))
            for col in element.findall(".//" + qn("w:tblGrid") + "/" + qn("w:gridCol"))
        ],
        "grid_span": [node.get(qn("w:val")) for node in element.findall(".//" + qn("w:gridSpan"))],
        "v_merge": [node.get(qn("w:val")) for node in element.findall(".//" + qn("w:vMerge"))],
    }


def add_field(paragraph, instruction: str, placeholder: str = "") -> None:
    from docx.oxml import OxmlElement

    run = paragraph.add_run()
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = instruction
    separate = OxmlElement("w:fldChar")
    separate.set(qn("w:fldCharType"), "separate")
    text = OxmlElement("w:t")
    text.text = placeholder
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    for element in (begin, instr, separate, text, end):
        run._r.append(element)
