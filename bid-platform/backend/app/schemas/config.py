from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import validate_blocks


class CompanyCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    name: str = Field(min_length=1, max_length=200)


class CompanyPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "draft", "archived"] | None = None


class CompanyRevisionCreate(BaseModel):
    fields_json: dict[str, Any] = Field(default_factory=dict)


class ProductCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z0-9_-]{1,50}$")
    name: str = Field(min_length=1, max_length=200)


class ProductPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    status: Literal["active", "draft", "archived"] | None = None


class ProductRevisionCreate(BaseModel):
    fields_json: dict[str, Any] = Field(default_factory=dict)
    technical_fields_json: dict[str, Any] = Field(default_factory=dict)


class RedlineCreate(BaseModel):
    scope_type: Literal["company", "product"]
    scope_id: str
    category: str = Field(min_length=1, max_length=100)
    position: str = Field(min_length=1, max_length=500)
    condition_json: dict[str, Any] = Field(default_factory=dict)
    action: str = Field(min_length=1, max_length=500)
    legal_review: bool = False
    revision_no: int = Field(default=1, ge=1)
    status: Literal["draft", "published"] = "draft"


class RedlinePatch(BaseModel):
    category: str | None = Field(default=None, min_length=1, max_length=100)
    position: str | None = Field(default=None, min_length=1, max_length=500)
    condition_json: dict[str, Any] | None = None
    action: str | None = Field(default=None, min_length=1, max_length=500)
    legal_review: bool | None = None
    status: Literal["draft", "published", "archived"] | None = None


def validate_template_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(nodes, list):
        raise ValueError("模板节点必须是数组")
    for node in nodes:
        if not isinstance(node, dict) or not str(node.get("title", "")).strip():
            raise ValueError("模板节点缺少标题")
        content = node.get("content_json") or []
        validate_blocks(content)
        children = node.get("children") or []
        validate_template_nodes(children)
    return nodes


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    project_type: str = Field(min_length=1, max_length=80)
    nodes_json: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator("nodes_json")
    @classmethod
    def valid_nodes(cls, value):
        return validate_template_nodes(value)


class TemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    project_type: str | None = Field(default=None, min_length=1, max_length=80)
    status: Literal["active", "draft", "archived"] | None = None


class TemplateRevisionCreate(BaseModel):
    nodes_json: list[dict[str, Any]]
    rules_version: str = "v1"

    @field_validator("nodes_json")
    @classmethod
    def valid_nodes(cls, value):
        return validate_template_nodes(value)
