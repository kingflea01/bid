from typing import Literal

from pydantic import Field

from app.schemas.common import VersionedRequest


class SnapshotCreate(VersionedRequest):
    label: str | None = Field(default=None, max_length=100)


class ExportCreate(VersionedRequest):
    snapshot_id: str
    export_kind: Literal["review", "formal"]
    format: Literal["docx", "pdf"]
    include_sources: bool = False
