from pydantic import BaseModel, Field, model_validator

from app.schemas.common import VersionedRequest


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=240)
    code: str = Field(pattern=r"^[A-Za-z0-9_.-]{2,80}$")
    customer_name: str = Field(min_length=1, max_length=200)
    procurement_type: str = Field(min_length=1, max_length=60)
    package: str | None = Field(default=None, max_length=60)
    package_name: str | None = Field(default=None, max_length=60)
    industry: str | None = Field(default=None, max_length=100)
    project_type: str | None = Field(default=None, max_length=80)
    company_revision_id: str
    product_revision_id: str
    template_revision_id: str
    source_project_id: str | None = None

    @model_validator(mode="after")
    def synchronize_package(self):
        if self.package is None and self.package_name is not None:
            self.package = self.package_name
        if self.package_name is None:
            self.package_name = self.package
        return self


class ProjectAction(VersionedRequest):
    document_id: str | None = None


class MemberCreate(BaseModel):
    user_id: str
    project_role: str = Field(pattern=r"^(editor|reviewer|viewer)$")
    version: int | None = None


class MemberPatch(BaseModel):
    project_role: str = Field(pattern=r"^(editor|reviewer|viewer)$")
    version: int | None = None
