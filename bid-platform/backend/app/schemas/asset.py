from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.common import validate_blocks


class AssetCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    title: str = Field(min_length=1, max_length=240)
    asset_type: str = Field(min_length=1, max_length=60)
    scope: Literal["company", "industry", "product", "customer"] = "company"
    industry: str | None = Field(default=None, max_length=100)
    project_type: str | None = Field(default=None, max_length=80)
    product_id: str | None = None
    customer_name: str | None = Field(default=None, max_length=200)
    section_key: str | None = Field(default=None, max_length=240)
    classification: Literal["public", "internal", "confidential"] = "internal"
    owner_id: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    status: Literal["active", "draft"] = "draft"

    @model_validator(mode="before")
    @classmethod
    def translate_scope(cls, value):
        if isinstance(value, dict):
            aliases = {
                "企业通用": "company",
                "行业": "industry",
                "产品线": "product",
                "客户专属": "customer",
            }
            if value.get("scope") in aliases:
                value = {**value, "scope": aliases[value["scope"]]}
        return value


class AssetVariantCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,60}$")
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)


class AssetRevisionCreate(BaseModel):
    content_json: list[dict[str, Any]]
    source_format: Literal["blocks", "structured_blocks", "docx"] = "blocks"

    @field_validator("content_json")
    @classmethod
    def valid_content(cls, value):
        return validate_blocks(value)
