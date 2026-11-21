import json

from app.core.database import SessionLocal
from app.models.risk import Risk
from tests.fixtures.documents import tender_docx_bytes, text_pdf_bytes
from tests.helpers import upload_and_parse


def test_creation_wizard_task_and_workspace_contract(client, project):
    upload = client.post(
        f"/api/v1/projects/{project['id']}/tender-documents",
        files={
            "file": (
                "tender.docx",
                tender_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    parsed = client.post(f"/api/v1/projects/{project['id']}:parse", json={"version": 1})
    assert parsed.status_code == 202, parsed.text
    parse_body = parsed.json()
    assert parse_body["task_id"] == parse_body["id"]
    assert parse_body["tasks"][0]["task_type"] == "parse"
    assert parse_body["status"] == "succeeded", parse_body
    analyzed = client.post(f"/api/v1/projects/{project['id']}:analyze", json={"version": 1})
    assert analyzed.status_code == 202, analyzed.text
    analysis_body = analyzed.json()
    assert analysis_body["task_ids"] == [analysis_body["id"]]
    assert analysis_body["tasks"][0]["task_type"] == "ai_analysis"
    assert analysis_body["status"] == "failed"

    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    for key in ("requirements", "activities", "snapshots", "export_readiness"):
        assert key in workspace
    assert workspace["project"]["package_name"] is None
    assert workspace["project"]["config_refs"]["company_revision_id"]
    assert workspace["activities"]
    assert workspace["tasks"][0]["task_type"] in {"ai_analysis", "parse"}
    assert all("version" in fact for fact in workspace["facts"])
    assert workspace["export_readiness"]["can_export_review"] is True
    assert workspace["export_readiness"]["can_export_formal"] is False
    assert workspace["snapshots"] == []
    task = client.get(f"/api/v1/tasks/{analysis_body['task_id']}").json()
    assert task["task_type"] == "ai_analysis"


def test_project_and_config_list_contracts(client, project, published_config):
    filtered = client.get(
        "/api/v1/projects", params={"keyword": "示例", "page": 1, "page_size": 20}
    )
    assert filtered.status_code == 200
    body = filtered.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == project["id"]
    assert "config_refs" in body["items"][0]
    empty = client.get("/api/v1/projects", params={"keyword": "不存在", "page_size": 20}).json()
    assert empty["total"] == 0 and empty["items"] == []
    default_list = client.get("/api/v1/projects")
    assert isinstance(default_list.json(), list)

    companies = client.get("/api/v1/companies").json()
    products = client.get("/api/v1/products").json()
    templates = client.get("/api/v1/templates").json()
    assert companies[0]["revisions"][0]["status"] == "published"
    assert products[0]["revisions"][0]["technical_fields_json"]
    assert templates[0]["revisions"][0]["nodes_json"]
    assets = client.get("/api/v1/assets", params={"asset_type": "technical"}).json()
    assert assets[0]["variants"][0]["revisions"][0]["content_json"]

    created_asset = client.post(
        "/api/v1/assets",
        json={
            "code": "FRONT-ASSET",
            "title": "前端中文范围素材",
            "asset_type": "实施方案",
            "scope": "企业通用",
            "status": "active",
        },
    )
    assert created_asset.status_code == 201, created_asset.text
    assert created_asset.json()["scope"] == "company"
    variant = client.post(
        f"/api/v1/assets/{created_asset.json()['id']}/variants",
        json={"code": "standard", "name": "标准方案", "description": ""},
    ).json()
    revision = client.post(
        f"/api/v1/variants/{variant['id']}/revisions",
        json={
            "content_json": [{"type": "paragraph", "text": "结构化正文"}],
            "source_format": "structured_blocks",
        },
    )
    assert revision.status_code == 201, revision.text
    assert revision.json()["source_format"] == "structured_blocks"

    redline = client.post(
        "/api/v1/redline-rules",
        json={
            "scope_type": "company",
            "scope_id": published_config["company"]["id"],
            "category": "合同责任",
            "position": "责任上限不超过合同金额",
            "condition_json": {"field": "liability_cap"},
            "action": "需要法务复核后协商",
            "legal_review": True,
            "revision_no": 2,
            "status": "draft",
        },
    )
    assert redline.status_code == 201, redline.text
    assert redline.json()["revision_no"] == 2
    published = client.patch(
        f"/api/v1/redline-rules/{redline.json()['id']}", json={"status": "published"}
    )
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    archived = client.patch(
        f"/api/v1/redline-rules/{redline.json()['id']}", json={"status": "archived"}
    )
    assert archived.status_code == 200

    attachment = client.post(
        f"/api/v1/assets/{published_config['asset']['id']}/attachments",
        files={"file": ("proof.pdf", text_pdf_bytes(False), "application/pdf")},
        data={"attachment_type": "证书扫描件", "valid_to": "2027-12-31"},
    )
    assert attachment.status_code == 201, attachment.text
    assert attachment.json()["valid_to"] == "2027-12-31"


def test_candidate_raw_id_diff_and_select_contract(client, project):
    _, workspace = upload_and_parse(client, project)
    section = next(
        item
        for item in workspace["sections"]
        if item["source_type"] == "tender" and "技术方案" in item["title"]
    )
    candidates = client.get(f"/api/v1/sections/{section['id']}/candidates").json()
    asset = next(candidate for candidate in candidates if candidate["candidate_type"] == "asset")
    assert asset["name"]
    assert asset["source_label"]
    assert isinstance(asset["rank_reasons"], list)
    assert "current" in asset

    diff = client.get(
        f"/api/v1/sections/{section['id']}/diff", params={"candidate_id": asset["candidate_id"]}
    )
    assert diff.status_code == 200, diff.text
    body = diff.json()
    assert body["section_id"] == section["id"]
    assert body["candidate_revision_id"] == asset["candidate_id"]
    assert body["current_revision_id"] == section["selected_revision_id"]
    assert isinstance(body["changes"], list) and body["changes"]
    assert body["changes"][0]["type"] in {"modified", "added", "removed", "unchanged"}
    assert "diff" in body and body["diff"]["changed"] is True

    current = client.get(f"/api/v1/projects/{project['id']}").json()
    selected = client.post(
        f"/api/v1/sections/{section['id']}:select-version",
        json={
            "candidate_id": asset["candidate_id"],
            "version": section["version"],
            "project_version": current["version"],
        },
    )
    assert selected.status_code == 200, selected.text
    selected_body = selected.json()
    assert selected_body["id"] == selected_body["revision"]["id"]
    assert selected_body["section_id"] == section["id"]
    assert selected_body["revision_no"] >= 2
    assert selected_body["source_asset_revision_id"] == asset["candidate_id"]
    assert selected_body["source_label"]
    assert "impacted_sections" in selected_body


def test_section_fact_gap_and_risk_frontend_contracts(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    saved = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "placeholder", "label": "待编写：前端占位"}],
            "base_version": section["version"],
            "version": section["version"],
        },
    )
    assert saved.status_code == 201, saved.text
    block = saved.json()["content_json"][0]
    assert block["label"] == "待编写：前端占位"
    assert block["text"] == "[[待编写：前端占位]]"

    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    section = next(item for item in workspace["sections"] if item["id"] == section["id"])
    gap = next(gap for gap in workspace["gaps"] if gap["title"] == "待编写：前端占位")
    ready = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "paragraph", "text": "前端编辑后的正文"}],
            "base_version": section["version"],
            "version": section["version"],
        },
    )
    assert ready.status_code == 201, ready.text
    resolved = client.post(
        f"/api/v1/gaps/{gap['id']}:resolve",
        json={
            "resolution_json": {"resolution_type": "text", "note": "已提交人工澄清与实际解决依据"}
        },
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolution_json"]["resolution_type"] == "text"

    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    section = next(item for item in workspace["sections"] if item["id"] == section["id"])
    fact = workspace["facts"][0]
    updated_fact = client.patch(
        f"/api/v1/projects/{project['id']}/facts/{fact['fact_key']}",
        json={
            "value_json": fact["value_json"],
            "value_type": fact["value_type"],
            "status": "confirmed",
            "version": fact["version"],
        },
    )
    assert updated_fact.status_code == 200, updated_fact.text
    assert updated_fact.json()["value_json"] == fact["value_json"]
    assert updated_fact.json()["fact"]["fact_key"] == fact["fact_key"]
    assert updated_fact.json()["version"]

    confirmed = client.post(
        f"/api/v1/sections/{section['id']}:confirm",
        json={
            "selected_revision_id": section["selected_revision_id"],
            "version": section["version"],
        },
    )
    assert confirmed.status_code == 200, confirmed.text
    with SessionLocal() as db:
        risk = Risk(
            project_id=project["id"],
            category="付款方式",
            conflict_type="ambiguous",
            severity="medium",
            recommendation="建议书面澄清",
            legal_review=False,
        )
        db.add(risk)
        db.commit()
        risk_id = risk.id
    disposed = client.post(
        f"/api/v1/risks/{risk_id}:disposition",
        json={"disposition": "mitigated", "disposition_note": "已取得采购人书面澄清并完成复核"},
    )
    assert disposed.status_code == 200, disposed.text
    assert disposed.json()["disposition"] == "mitigated"
    assert disposed.json()["disposition_note"]
    assert "requirement_text" in disposed.json()


def test_snapshot_export_readiness_and_export_list_contract(client, project):
    upload_and_parse(client, project)
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots",
        json={"label": "前端审阅快照", "version": current["version"]},
    )
    assert snapshot.status_code == 201, snapshot.text
    snapshot_body = snapshot.json()
    assert snapshot_body["label"] == "前端审阅快照"
    assert snapshot_body["created_by_name"] == "管理员"
    assert snapshot_body["formal_ready"] is False
    assert snapshot_body["qa_json"]["blockers"]

    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    readiness = workspace["export_readiness"]
    assert readiness["can_export_review"] is True
    assert readiness["current_snapshot_id"] == snapshot_body["id"]
    assert readiness["checks"]
    assert workspace["snapshots"][0]["label"] == "前端审阅快照"
    assert any(activity.get("actor_name") for activity in workspace["activities"])

    exported = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={"snapshot_id": snapshot_body["id"], "export_kind": "review", "format": "docx"},
    )
    assert exported.status_code == 202, exported.text
    assert exported.json()["snapshot_no"] == snapshot_body["snapshot_no"]
    tasks = client.get(f"/api/v1/projects/{project['id']}/exports")
    assert tasks.status_code == 200
    assert tasks.json()[0]["snapshot_no"] == snapshot_body["snapshot_no"]
    snapshots = client.get(f"/api/v1/projects/{project['id']}/snapshots").json()
    assert snapshots[0]["qa_json"]["stats"]
    assert client.get(f"/api/v1/projects/{project['id']}").json()["status"] == "review"


def test_multipart_gap_attachment_and_block_aliases(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    saved = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "placeholder", "label": "附件：前端证明"}],
            "base_version": section["version"],
            "version": section["version"],
        },
    )
    assert saved.status_code == 201, saved.text
    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    gap = next(gap for gap in workspace["gaps"] if gap["title"] == "附件：前端证明")
    resolution = {
        "resolution_type": "attachment",
        "note": "已上传前端证明文件并核对有效期",
    }
    resolved = client.post(
        f"/api/v1/gaps/{gap['id']}:resolve",
        files={"file": ("proof.pdf", text_pdf_bytes(False), "application/pdf")},
        data={"resolution_json": json.dumps(resolution, ensure_ascii=False)},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolution_json"]["attachment_id"]
    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    section = next(item for item in workspace["sections"] if item["id"] == section["id"])
    block = section["selected_revision"]["content_json"][0]
    assert block["attachment_id"] == block["file_id"]
    assert block["label"] == block["name"] == "前端证明"


def test_move_rename_package_and_source_contract(client, project, published_config):
    document, workspace = upload_and_parse(client, project)
    section = next(
        item for item in workspace["sections"] if item["source_type"] == "user_supplement"
    )
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    moved = client.post(
        f"/api/v1/sections/{section['id']}:move",
        json={
            "parent_id": section["parent_id"],
            "position": 0,
            "version": section["version"],
            "project_version": current["version"],
        },
    )
    assert moved.status_code == 200, moved.text
    renamed = client.patch(
        f"/api/v1/sections/{section['id']}",
        json={"title": "前端补充方案", "version": moved.json()["version"]},
    )
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["title"] == "前端补充方案"

    anchor = workspace["sections"][0]["source_anchor"]
    source = client.get(f"/api/v1/tender-documents/{document['id']}/anchors/{anchor}")
    assert source.status_code == 200
    assert source.json()["document_name"] == "tender.docx"
    assert source.json()["outline_title"]

    packaged = client.post(
        "/api/v1/projects",
        json={
            "name": "前端分包项目",
            "code": "FRONT-PACKAGE",
            "customer_name": "示例客户",
            "procurement_type": "公开招标",
            "package_name": "第 03 包",
            "company_revision_id": published_config["company_revision_id"],
            "product_revision_id": published_config["product_revision_id"],
            "template_revision_id": published_config["template_revision_id"],
        },
    )
    assert packaged.status_code == 201, packaged.text
    assert packaged.json()["package"] == "第 03 包"
    assert packaged.json()["package_name"] == "第 03 包"
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin" and me.json()["active"] is True
