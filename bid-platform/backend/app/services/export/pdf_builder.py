import subprocess
import tempfile
from pathlib import Path

import fitz

from app.core.config import get_settings
from app.core.errors import AppError


def convert_docx_to_pdf(data: bytes) -> tuple[bytes, dict]:
    settings = get_settings()
    try:
        with tempfile.TemporaryDirectory(prefix="bid-pdf-") as directory:
            root = Path(directory)
            source = root / "snapshot.docx"
            source.write_bytes(data)
            profile = (root / "profile").as_uri()
            command = [
                settings.libreoffice_binary,
                f"-env:UserInstallation={profile}",
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(root),
                str(source),
            ]
            process = subprocess.run(command, capture_output=True, timeout=240, check=False)
            target = root / "snapshot.pdf"
            if process.returncode != 0 or not target.is_file():
                raise AppError(502, "pdf_conversion_failed", "LibreOffice PDF 转换失败")
            pdf = target.read_bytes()
    except FileNotFoundError as exc:
        raise AppError(
            503, "pdf_converter_unavailable", "LibreOffice 不可用，DOCX 导出不受影响"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(504, "pdf_conversion_timeout", "PDF 转换超时") from exc
    try:
        document = fitz.open(stream=pdf, filetype="pdf")
        with document:
            pages = len(document)
            text_by_page = [page.get_text().strip() for page in document]
        if pages == 0 or not any(text_by_page):
            raise AppError(502, "pdf_validation_failed", "PDF 完整性或文本可提取性校验失败")
        blank_pages = [index + 1 for index, text in enumerate(text_by_page) if not text]
        return pdf, {
            "page_count": pages,
            "blank_pages": blank_pages,
            "text_extractable": True,
            "passed": True,
        }
    except AppError:
        raise
    except Exception as exc:
        raise AppError(502, "pdf_validation_failed", "PDF 完整性校验失败") from exc
