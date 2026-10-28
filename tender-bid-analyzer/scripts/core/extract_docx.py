#!/usr/bin/env python3
"""Extract paragraphs and tables from a .docx file into a line-oriented text file.

Usage:
    python3 extract_docx.py input.docx output.txt
"""

import argparse
import re
import sys
import zipfile
from pathlib import Path

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def iter_docx_blocks(document):
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    for child in document.element.body.iterchildren():
        if child.tag.endswith("}p"):
            yield Paragraph(child, document)
        elif child.tag.endswith("}tbl"):
            yield Table(child, document)


def extract_with_docx(path):
    import docx

    document = docx.Document(str(path))
    lines = []
    table_no = 0

    for block in iter_docx_blocks(document):
        if block.__class__.__name__ == "Paragraph":
            text = block.text.strip()
            if text:
                lines.append(text)
            continue

        table_no += 1
        lines.append(f"[TABLE {table_no}]")
        for row in block.rows:
            cells = []
            previous_tc = None
            for cell in row.cells:
                if cell._tc is previous_tc:
                    continue
                previous_tc = cell._tc
                cells.append(cell.text.strip().replace("\n", " / "))
            lines.append(" | ".join(cells))
        lines.append("[/TABLE]")

    return "\n".join(lines), table_no


def extract_with_xml(path):
    from xml.etree import ElementTree as ET

    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")

    root = ET.fromstring(xml)
    body = root.find(f"{{{W_NS}}}body")
    if body is None:
        raise ValueError("word/document.xml has no w:body")

    lines = []
    table_no = 0

    for child in body:
        tag = child.tag.split("}")[-1]
        if tag == "p":
            text = "".join(node.text or "" for node in child.iter(f"{{{W_NS}}}t")).strip()
            if text:
                lines.append(text)
        elif tag == "tbl":
            table_no += 1
            lines.append(f"[TABLE {table_no}]")
            for row in child.findall(f"{{{W_NS}}}tr"):
                cells = []
                for cell in row.findall(f"{{{W_NS}}}tc"):
                    text = "".join(
                        node.text or "" for node in cell.iter(f"{{{W_NS}}}t")
                    ).strip()
                    cells.append(text.replace("\n", " / "))
                lines.append(" | ".join(cells))
            lines.append("[/TABLE]")

    return "\n".join(lines), table_no


def count_embedded_assets(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    media = sum(1 for name in names if name.startswith("word/media/"))
    embeddings = sum(1 for name in names if name.startswith("word/embeddings/"))
    return media, embeddings


def main():
    parser = argparse.ArgumentParser(description="Extract text and tables from a .docx")
    parser.add_argument("input", help="input .docx path")
    parser.add_argument("output", help="output .txt path")
    args = parser.parse_args()

    source = Path(args.input)
    target = Path(args.output)

    if not source.exists():
        print(f"ERROR: file not found: {source}", file=sys.stderr)
        return 2
    if source.suffix.lower() == ".doc":
        print(
            "ERROR: legacy .doc is not supported. Convert first: "
            f'soffice --headless --convert-to docx "{source}"',
            file=sys.stderr,
        )
        return 2
    if source.suffix.lower() != ".docx":
        print("ERROR: input must be a .docx file", file=sys.stderr)
        return 2

    try:
        text, table_count = extract_with_docx(source)
        method = "python-docx"
    except ImportError:
        text, table_count = extract_with_xml(source)
        method = "raw-xml fallback"
    except Exception as exc:
        print(f"WARN: python-docx failed ({exc}); trying raw XML", file=sys.stderr)
        text, table_count = extract_with_xml(source)
        method = "raw-xml fallback"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")

    media, embeddings = count_embedded_assets(source)
    print(f"method: {method}")
    print(f"tables: {table_count}")
    print(f"characters: {len(text)}")
    print(f"media files: {media}")
    print(f"embedded objects: {embeddings}")
    print(f"output: {target}")
    if media or embeddings:
        print(
            "WARN: media/embedded objects were not extracted. "
            "Check attachments and embedded files manually."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
