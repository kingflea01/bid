"""Clone body blocks from the tender DOCX into the bid DOCX."""

import copy

from docx.oxml.ns import qn


def body_items(document):
    body = document.element.body
    paragraph_map = {
        body.index(paragraph._p): ("p", index)
        for index, paragraph in enumerate(document.paragraphs)
    }
    table_map = {
        body.index(table._tbl): ("tbl", index)
        for index, table in enumerate(document.tables)
    }
    items = []
    for position, child in enumerate(body.iterchildren()):
        tag = child.tag.split("}")[-1]
        if tag == "p" and position in paragraph_map:
            items.append(
                {"kind": "p", "index": paragraph_map[position][1], "element": child}
            )
        elif tag == "tbl" and position in table_map:
            items.append(
                {"kind": "tbl", "index": table_map[position][1], "element": child}
            )
    return items


def clear_body(document):
    body = document.element.body
    for child in list(body):
        if not child.tag.endswith("sectPr"):
            body.remove(child)


def block_elements(document, start_index, end_index):
    if start_index is None:
        return []
    items = body_items(document)
    start_pos = None
    for position, item in enumerate(items):
        if item["kind"] == "p" and item["index"] == start_index:
            start_pos = position
            break
    if start_pos is None:
        return []

    elements = []
    for item in items[start_pos + 1:]:
        if end_index is not None and item["kind"] == "p" and item["index"] == end_index:
            break
        elements.append(item["element"])
    return elements


def clone_elements(target_document, elements):
    body = target_document.element.body
    sect_pr = body.find(qn("w:sectPr"))
    cloned = []
    for element in elements:
        new_element = copy.deepcopy(element)
        if sect_pr is not None:
            sect_pr.addprevious(new_element)
        else:
            body.append(new_element)
        cloned.append(new_element)
    return cloned
