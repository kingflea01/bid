from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import VersionedRequest, validate_blocks


class SectionPatch(VersionedRequest):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    content_mode: Literal["fixed_text", "placeholder", "tender_template"] | None = None


class SectionMove(VersionedRequest):
    parent_id: str | None = None
    position: int = Field(ge=0)


class SectionRevisionCreate(VersionedRequest):
    content_json: list[dict[str, Any]]
    base_version: int | None = None

    @field_validator("content_json")
    @classmethod
    def valid_content(cls, value):
        return validate_blocks(value)


class SelectVersion(VersionedRequest):
    candidate_id: str


class ConfirmSection(VersionedRequest):
    selected_revision_id: str | None = None


class GapResolve(VersionedRequest):
    resolution_type: Literal["manual", "text", "asset", "attachment"]
    note: str = Field(min_length=2, max_length=4000)
    asset_revision_id: str | None = None
    file_id: str | None = None
    attachment_id: str | None = None


class RiskDisposition(VersionedRequest):
    disposition: Literal[
        "accepted", "mitigated", "negotiating", "rejected", "clarified", "resolved"
    ]
    note: str | None = Field(default=None, min_length=2, max_length=4000)
    disposition_note: str | None = Field(default=None, min_length=2, max_length=4000)

    @model_validator(mode="after")
    def require_note(self):
        if not self.note and not self.disposition_note:
            raise ValueError("必须填写处置依据")
        return self

    @property
    def resolution_note(self) -> str:
        return self.disposition_note or self.note or ""


class FactUpdate(VersionedRequest):
    value: Any = None
    value_json: Any = None
    value_type: Literal["string", "number", "boolean", "date", "json"] = "string"
    status: Literal["unconfirmed", "confirmed"] = "unconfirmed"

    @model_validator(mode="after")
    def synchronize_value(self):
        if self.value is None and self.value_json is None:
            raise ValueError("必须提供 value 或 value_json")
        if self.value is None:
            self.value = self.value_json
        if self.value_json is None:
            self.value_json = self.value
        return self
