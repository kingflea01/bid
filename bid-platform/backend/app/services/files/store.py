import hashlib
import os
import re
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import bad_request, not_found
from app.models.tender import StoredFile

SAFE_SUFFIXES = {".docx", ".pdf", ".png", ".jpg", ".jpeg"}


class FileStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or get_settings().file_storage_path).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        db: Session,
        data: bytes,
        original_name: str,
        mime_type: str,
        uploaded_by: str | None,
    ) -> StoredFile:
        if not data:
            raise bad_request("不能上传空文件", code="empty_file")
        maximum = get_settings().max_upload_bytes
        if len(data) > maximum:
            raise bad_request("文件超过大小限制", code="file_too_large")
        suffix = Path(original_name).suffix.lower()
        if suffix not in SAFE_SUFFIXES:
            raise bad_request("不支持的文件扩展名", code="unsupported_file_type")
        digest = hashlib.sha256(data).hexdigest()
        existing = db.scalar(select(StoredFile).where(StoredFile.sha256 == digest))
        if existing:
            return existing
        directory = self.root / digest[:2]
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / f".{digest}.{os.getpid()}.tmp"
        target = directory / f"{digest}{suffix}"
        try:
            temporary.write_bytes(data)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        record = StoredFile(
            sha256=digest,
            path=str(target.relative_to(self.root)),
            mime_type=mime_type,
            size=len(data),
            original_name=Path(original_name).name[:500],
            uploaded_by=uploaded_by,
        )
        db.add(record)
        db.flush()
        return record

    def path_for(self, record: StoredFile) -> Path:
        path = (self.root / record.path).resolve()
        if self.root not in path.parents or not path.is_file():
            raise not_found("文件")
        return path

    def read(self, record: StoredFile) -> bytes:
        return self.path_for(record).read_bytes()


def validate_signature(filename: str, claimed_mime: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".docx":
        if not data.startswith(b"PK\x03\x04"):
            raise bad_request("DOCX 文件签名无效", code="invalid_file_signature")
        allowed = {
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/zip",
            "application/octet-stream",
        }
        if claimed_mime and claimed_mime not in allowed:
            raise bad_request("DOCX MIME 类型无效", code="unsupported_file_type")
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise bad_request("PDF 文件签名无效", code="invalid_file_signature")
        if claimed_mime and claimed_mime not in {"application/pdf", "application/octet-stream"}:
            raise bad_request("PDF MIME 类型无效", code="unsupported_file_type")
        return "application/pdf"
    signatures = {
        ".png": b"\x89PNG\r\n\x1a\n",
        ".jpg": b"\xff\xd8\xff",
        ".jpeg": b"\xff\xd8\xff",
    }
    if suffix in signatures and data.startswith(signatures[suffix]):
        return "image/png" if suffix == ".png" else "image/jpeg"
    raise bad_request("文件类型或签名无效", code="invalid_file_signature")


def safe_export_name(name: str, suffix: str) -> str:
    cleaned = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", name).strip("._") or "bid"
    return f"{cleaned[:120]}.{suffix}"
