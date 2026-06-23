#!/usr/bin/env python3
"""
招标文件解析工具 — 输出结构化JSON（含 plain_text 字段）
Usage: python3 extractor.py <file_path>
"""

import sys
import os
import json
import subprocess
import shutil
from pathlib import Path


def detect_type(filepath: str) -> str:
    """检测文件类型"""
    ext = os.path.splitext(filepath)[1].lower()
    if ext == ".pdf":
        return "pdf"
    if ext == ".docx":
        return "docx"
    if ext == ".doc":
        return "doc"
    if ext in (".html", ".htm"):
        return "html"
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp"):
        return "image"
    if ext == ".txt":
        return "txt"

    result = subprocess.run(["file", "--mime-type", filepath], capture_output=True, text=True)
    mime = result.stdout.strip().split(":")[-1].strip()
    if "pdf" in mime:
        return "pdf"
    if "wordprocessingml" in mime:
        return "docx"
    if "msword" in mime:
        return "doc"
    if "html" in mime:
        return "html"
    if "text/plain" in mime:
        return "txt"
    return "unknown"


# === 降级用纯文本提取函数（仅用于不支持结构化提取的格式） ===


def extract_text_doc(filepath: str) -> str:
    """从旧版Word文档提取纯文本"""
    textutil = shutil.which("textutil")
    if textutil:
        outpath = filepath + ".txt"
        subprocess.run([textutil, "-convert", "txt", "-output", outpath, filepath], check=True)
        with open(outpath, encoding="utf-8") as f:
            text = f.read()
        os.remove(outpath)
        return text
    libre = shutil.which("libreoffice")
    if libre:
        outdir = os.path.dirname(os.path.abspath(filepath))
        subprocess.run(
            [libre, "--headless", "--convert-to", "txt", "--outdir", outdir, filepath],
            check=True, capture_output=True
        )
        outpath = os.path.splitext(filepath)[0] + ".txt"
        with open(outpath, encoding="utf-8") as f:
            text = f.read()
        os.remove(outpath)
        return text
    raise RuntimeError("No tool available to extract .doc files. Install textutil (macOS) or libreoffice.")


def extract_text_html(filepath: str) -> str:
    """从HTML提取纯文本"""
    result = subprocess.run(["python3", "-m", "html2text", filepath], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout
    from html.parser import HTMLParser
    class TextOnly(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
        def handle_data(self, data):
            self.text.append(data)
    p = TextOnly()
    with open(filepath) as f:
        p.feed(f.read())
    return "\n".join(p.text)


def extract_text_image(filepath: str) -> str:
    """从图片提取纯文本（OCR）"""
    tesseract = shutil.which("tesseract")
    if not tesseract:
        raise RuntimeError("tesseract not found. Install with: brew install tesseract")
    result = subprocess.run([tesseract, filepath, "stdout", "-l", "chi_sim+eng"], capture_output=True, text=True)
    return result.stdout



# === 结构化JSON提取函数 ===

def heading_level(style_name):
    """识别标题级别"""
    for i in range(1, 7):
        if style_name == f"Heading {i}":
            return i
    return None


def parse_paragraph(para):
    """解析段落为结构化数据"""
    style_name = para.style.name if para.style else ""
    text = para.text.strip()
    level = heading_level(style_name)
    return {
        "type": "paragraph",
        "style": style_name,
        "text": text,
        "is_heading": level is not None,
        "heading_level": level
    }


def parse_table(table):
    """解析表格为结构化数据"""
    rows = []
    for row in table.rows:
        cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
        rows.append(cells)
    if not rows:
        return None
    col_count = max(len(r) for r in rows)
    for r in rows:
        while len(r) < col_count:
            r.append("")
    return {
        "type": "table",
        "rows": rows
    }


def extract_json_docx(filepath: str) -> list:
    """从Word文档提取结构化数据"""
    from docx import Document
    doc = Document(filepath)
    elements = []
    for element in doc.element.body:
        tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag
        if tag == "p":
            for para in doc.paragraphs:
                if para._element is element:
                    result = parse_paragraph(para)
                    elements.append(result)
                    break
        elif tag == "tbl":
            for table in doc.tables:
                if table._element is element:
                    result = parse_table(table)
                    if result:
                        elements.append(result)
                    break
    return elements


def extract_json_pdf(filepath: str) -> list:
    """从PDF提取结构化数据（简化版，按页分割）"""
    import fitz
    doc = fitz.open(filepath)
    elements = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        if text:
            # 按段落分割
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para_text in paragraphs:
                elements.append({
                    "type": "paragraph",
                    "style": "Normal",
                    "text": para_text,
                    "is_heading": False,
                    "heading_level": None
                })
    doc.close()
    return elements


def extract_json_txt(filepath: str) -> list:
    """从纯文本文件提取结构化数据"""
    with open(filepath, encoding="utf-8") as f:
        text = f.read()
    
    elements = []
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para_text in paragraphs:
        elements.append({
            "type": "paragraph",
            "style": "Normal",
            "text": para_text,
            "is_heading": False,
            "heading_level": None
        })
    return elements


# === 主函数 ===

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 extractor.py <file_path>", file=sys.stderr)
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    if not os.path.isfile(filepath):
        print(f"File not found: {filepath}", file=sys.stderr)
        sys.exit(1)
    
    ftype = detect_type(filepath)
    
    if ftype == "unknown":
        print(f"Cannot detect file type: {filepath}", file=sys.stderr)
        sys.exit(1)
    
    # 前置检查：验证所需依赖是否可用
    required_imports = {
        "docx": ("pdf", "docx"),     # extract_json_pdf 和 extract_json_docx 需要
        "fitz": ("pdf",),             # extract_json_pdf 需要
    }
    for module, needed_by in required_imports.items():
        if ftype in needed_by:
            try:
                __import__(module)
            except ImportError:
                print(f"Missing dependency: {module} (required for {ftype} files)", file=sys.stderr)
                if module == "docx":
                    print("Install with: pip3 install python-docx", file=sys.stderr)
                elif module == "fitz":
                    print("Install with: pip3 install pymupdf", file=sys.stderr)
                sys.exit(1)
    
    try:
        extractors = {
            "pdf": extract_json_pdf,
            "docx": extract_json_docx,
            "txt": extract_json_txt,
        }
        
        if ftype not in extractors:
            # 降级：不支持结构化提取的格式，使用纯文本包装
            print(f"JSON extraction not supported for format: {ftype}, falling back to text.", file=sys.stderr)
            text_extractors = {
                "doc": extract_text_doc,
                "html": extract_text_html,
                "image": extract_text_image,
            }
            if ftype not in text_extractors:
                print(f"Unsupported file type: {ftype}", file=sys.stderr)
                sys.exit(1)
            text = text_extractors[ftype](filepath)
            if not text or not text.strip():
                print(f"Warning: extracted text is empty for {filepath}", file=sys.stderr)
            result = {
                "source_file": os.path.basename(filepath),
                "file_type": ftype,
                "plain_text": text,
                "elements": [{
                    "type": "paragraph",
                    "style": "Normal",
                    "text": text,
                    "is_heading": False,
                    "heading_level": None
                }]
            }
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return
        
        elements = extractors[ftype](filepath)
        
        if not elements:
            print(f"Warning: no content extracted from {filepath} (0 elements)", file=sys.stderr)
        
        # 构建 plain_text：段落取 text，表格用 " | " 连接单元格、行间换行
        plain_parts = []
        for elem in elements:
            if elem["type"] == "paragraph":
                plain_parts.append(elem["text"])
            elif elem["type"] == "table":
                for row in elem["rows"]:
                    plain_parts.append(" | ".join(row))
        plain_text = "\n".join(plain_parts)
        
        result = {
            "source_file": os.path.basename(filepath),
            "file_type": ftype,
            "plain_text": plain_text,
            "elements": elements
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    except Exception as e:
        print(f"Extraction failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
