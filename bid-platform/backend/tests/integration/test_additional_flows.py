import io
import zipfile

import fitz
import pytest
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.errors import AppError
from app.models.project import Project, ProjectConfigRef
from app.models.risk import Risk
from app.models.tender import TenderDocument
from app.services.workspace.state import touch_project
from tests.fixtures.documents import tender_docx_bytes, text_pdf_bytes
from tests.helpers import confirm_ready_project, upload_and_parse


def test_published_revisions_are_immutable_and_old_project_baseline_is_stable(
    client, project, published_config
):
    company = published_config["company"]
    old_revision_id = published_config["company_revision_id"]
    new_revision = client.post(
        f"/api/v1/companies/{company['id']}/revisions",
        json={"fields_json": {"公司名称": "新供应商名称"}},
    ).json()
    assert client.post(f"/api/v1/company-revisions/{new_revision['id']}:publish").status_code == 200
    with SessionLocal() as db:
        refs = db.scalar(
            select(ProjectConfigRef).where(ProjectConfigRef.project_id == project["id"])
        )
        assert refs.company_revision_id == old_revision_id
    duplicate = client.post(
        "/api/v1/projects",
        json={
            "name": "使用旧配置的新项目",
            "code": "PRJ-OLD-CONFIG",
            "customer_name": "示例客户",
            "procurement_type": "公开招标",
            "company_revision_id": old_revision_id,
            "product_revision_id": published_config["product_revision_id"],
            "template_revision_id": published_config["template_revision_id"],
        },
    )
    assert duplicate.status_code == 400
    assert duplicate.json()["code"] == "unpublished_config"
    changed_redline = client.patch(
        f"/api/v1/redline-rules/{published_config['redline']['id']}",
        json={"position": "预付款不低于 30%"},
    )
    assert changed_redline.status_code == 200
    assert changed_redline.json()["revision_no"] == 2
    assert changed_redline.json()["status"] == "draft"
    unsafe_template = client.post(
        "/api/v1/templates",
        json={
            "name": "不安全模板",
            "project_type": "service",
            "nodes_json": [
                {
                    "title": "坏块",
                    "content_json": [{"type": "html", "html": "<script>alert(1)</script>"}],
                }
            ],
        },
    )
    assert unsafe_template.status_code == 422


def test_pdf_parse_confirmation_and_real_formal_pdf_export(client, project):
    upload = client.post(
        f"/api/v1/projects/{project['id']}/tender-documents",
        files={"file": ("tender.pdf", text_pdf_bytes(), "application/pdf")},
        data={"version": str(project["version"])},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    parsed = client.post(
        f"/api/v1/projects/{project['id']}:parse",
        json={"document_id": document["id"], "version": current["version"]},
    ).json()
    assert parsed["status"] == "succeeded", parsed
    assert parsed["result_json"]["scanned_pages"] == [2]
    assert parsed["result_json"]["parse_confirmed"] is False
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    confirmed = client.post(
        f"/api/v1/tender-documents/{document['id']}:confirm",
        json={"version": current["version"]},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["user_confirmed"] is True
    confirm_ready_project(client, project["id"])
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    exported = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": snapshot["id"],
            "export_kind": "formal",
            "format": "pdf",
            "version": current["version"],
        },
    )
    assert exported.status_code == 202, exported.text
    task = exported.json()
    assert task["status"] == "succeeded", task
    assert task["qa_json"]["pdf"]["text_extractable"] is True
    download = client.get(f"/api/v1/exports/{task['id']}/download")
    assert download.status_code == 200
    with fitz.open(stream=download.content, filetype="pdf") as pdf:
        assert len(pdf) >= 1
        assert any(page.get_text().strip() for page in pdf)


def test_parse_cache_and_renewal_history_rebinds_ooxml(client, project, published_config):
    source_bytes = tender_docx_bytes()
    first_document, first_workspace = upload_and_parse(client, project, source_bytes)
    confirm_ready_project(client, project["id"])
    second = client.post(
        "/api/v1/projects",
        json={
            "name": "续约项目",
            "code": "PRJ-RENEWAL",
            "customer_name": project["customer_name"],
            "procurement_type": "公开招标",
            "industry": "education",
            "project_type": "service",
            "source_project_id": project["id"],
            "company_revision_id": published_config["company_revision_id"],
            "product_revision_id": published_config["product_revision_id"],
            "template_revision_id": published_config["template_revision_id"],
        },
    ).json()
    second_document, second_workspace = upload_and_parse(client, second, source_bytes)
    with SessionLocal() as db:
        cached = db.get(TenderDocument, second_document["id"])
        assert cached.parse_qa_json["cache_hit"] is True
    section = next(
        item
        for item in second_workspace["sections"]
        if item["source_type"] == "tender" and "技术方案" in item["title"]
    )
    candidates = client.get(f"/api/v1/sections/{section['id']}/candidates").json()
    history = next(
        candidate
        for candidate in candidates
        if candidate["candidate_type"] == "history"
        and candidate["content_json"][0]["type"] == "tender_ooxml_ref"
    )
    assert history["content_json"][0]["document_id"] == second_document["id"]
    assert history["content_json"][0]["document_id"] != first_document["id"]
    current = client.get(f"/api/v1/projects/{second['id']}").json()
    selected = client.post(
        f"/api/v1/sections/{section['id']}:select-version",
        json={"candidate_id": history["id"], "version": current["version"]},
    )
    assert selected.status_code == 200, selected.text
    revision = selected.json()["revision"]
    assert revision["source_history_revision_id"] == history["candidate_id"]
    assert revision["content_json"][0]["document_id"] == second_document["id"]


def test_fact_propagation_and_gap_resolution(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    saved = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "fact_ref", "fact_key": "project_name"}],
            "version": current["version"],
        },
    )
    assert saved.status_code == 201, saved.text
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    changed = client.patch(
        f"/api/v1/projects/{project['id']}/facts/project_name",
        json={
            "value": "新项目名称",
            "value_type": "string",
            "status": "unconfirmed",
            "version": current["version"],
        },
    )
    assert changed.status_code == 200
    assert section["id"] in changed.json()["affected_section_ids"]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    placeholder = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [
                {"type": "placeholder", "name": "待编写：测试", "text": "[[待编写：测试]]"}
            ],
            "version": current["version"],
        },
    )
    assert placeholder.status_code == 201
    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    gap = next(gap for gap in workspace["gaps"] if gap["title"] == "待编写：测试")
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    ready = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "paragraph", "text": "已补齐正文"}],
            "version": current["version"],
        },
    )
    assert ready.status_code == 201
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    resolved = client.post(
        f"/api/v1/gaps/{gap['id']}:resolve",
        json={
            "resolution_type": "manual",
            "note": "已人工补齐并复核正文",
            "version": current["version"],
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "resolved"
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    confirmed = client.post(
        f"/api/v1/sections/{section['id']}:confirm", json={"version": current["version"]}
    )
    assert confirmed.status_code == 200, confirmed.text


def test_project_attachment_closes_gap_and_is_embedded(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    saved = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [
                {
                    "type": "placeholder",
                    "kind": "attachment",
                    "name": "附件：营业执照",
                    "text": "[[附件：营业执照]]",
                }
            ],
            "version": current["version"],
        },
    )
    assert saved.status_code == 201
    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    gap = next(gap for gap in workspace["gaps"] if gap["title"] == "附件：营业执照")
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    attachment = client.post(
        f"/api/v1/projects/{project['id']}/attachments",
        files={"file": ("license.pdf", text_pdf_bytes(with_scanned_page=False), "application/pdf")},
        data={"attachment_type": "license", "version": str(current["version"])},
    )
    assert attachment.status_code == 201, attachment.text
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    resolved = client.post(
        f"/api/v1/gaps/{gap['id']}:resolve",
        json={
            "resolution_type": "attachment",
            "note": "已上传有效营业执照",
            "file_id": attachment.json()["file_id"],
            "version": current["version"],
        },
    )
    assert resolved.status_code == 200, resolved.text
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    exported = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": snapshot["id"],
            "export_kind": "review",
            "format": "docx",
            "version": current["version"],
        },
    )
    assert exported.status_code == 202, exported.text
    download = client.get(f"/api/v1/exports/{exported.json()['id']}/download")
    assert download.status_code == 200
    with zipfile.ZipFile(io.BytesIO(download.content)) as archive:
        assert any(name.startswith("word/media/") for name in archive.namelist())


def test_atomic_project_version_rejects_stale_writer(client, project):
    with SessionLocal() as first, SessionLocal() as second:
        first_project = first.get(Project, project["id"])
        second_project = second.get(Project, project["id"])
        touch_project(first, first_project)
        first.commit()
        with pytest.raises(AppError) as error:
            touch_project(second, second_project)
        assert error.value.status_code == 409


def test_reviewer_disposition_is_required_for_formal_export(client, project):
    upload_and_parse(client, project)
    confirm_ready_project(client, project["id"])
    with SessionLocal() as db:
        risk = Risk(
            project_id=project["id"],
            category="付款方式",
            conflict_type="explicit",
            severity="high",
            recommendation="协商付款节点",
            legal_review=False,
        )
        db.add(risk)
        db.commit()
        risk_id = risk.id
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    first_snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    blocked = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": first_snapshot["id"],
            "export_kind": "formal",
            "format": "docx",
            "version": current["version"],
        },
    )
    assert blocked.status_code == 422
    codes = {item["code"] for item in blocked.json()["details"]["qa"]["blockers"]}
    assert "pending_risks" in codes
    disposed = client.post(
        f"/api/v1/risks/{risk_id}:disposition",
        json={
            "disposition": "accepted",
            "note": "审阅人评估后接受该付款安排",
            "version": current["version"],
        },
    )
    assert disposed.status_code == 200, disposed.text
    assert disposed.json()["disposed_by"]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    second_snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    exported = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": second_snapshot["id"],
            "export_kind": "formal",
            "format": "docx",
            "version": current["version"],
        },
    )
    assert exported.status_code == 202, exported.text
    assert exported.json()["status"] == "succeeded", exported.json()
