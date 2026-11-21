import io

from docx import Document

from tests.helpers import confirm_ready_project, upload_and_parse


def test_docx_workspace_snapshot_and_formal_export(client, project):
    document, workspace = upload_and_parse(client, project)
    assert document["status"] == "parsed"
    assert len(workspace["sections"]) == 3
    assert workspace["summary"]["unconfirmed"] == 3
    tender_sections = [
        section for section in workspace["sections"] if section["source_type"] == "tender"
    ]
    assert len(tender_sections) == 2
    assert all(
        section["selected_revision"]["content_json"][0]["type"] == "tender_ooxml_ref"
        for section in tender_sections
    )
    anchor = workspace["sections"][0]["source_anchor"]
    source = client.get(f"/api/v1/tender-documents/{document['id']}/anchors/{anchor}")
    assert source.status_code == 200
    assert "响应函" in source.json()["text"]

    confirm_ready_project(client, project["id"])
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot_response = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    )
    assert snapshot_response.status_code == 201, snapshot_response.text
    snapshot = snapshot_response.json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    exported = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": snapshot["id"],
            "export_kind": "formal",
            "format": "docx",
            "version": current["version"],
            "include_sources": True,
        },
    )
    assert exported.status_code == 202, exported.text
    task = exported.json()
    assert task["status"] == "succeeded", task
    assert task["qa_json"]["ooxml_valid"] is True
    assert task["qa_json"]["placeholder_count"] == 0
    download = client.get(f"/api/v1/exports/{task['id']}/download")
    assert download.status_code == 200
    generated = Document(io.BytesIO(download.content))
    text = "\n".join(paragraph.text for paragraph in generated.paragraphs)
    assert "示例服务项目" in text
    assert "快照 #" in "\n".join(
        p.text for section in generated.sections for p in section.footer.paragraphs
    )


def test_review_export_allows_incomplete_and_formal_is_blocked(client, project):
    _, workspace = upload_and_parse(client, project)
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    blocked = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": snapshot["id"],
            "export_kind": "formal",
            "format": "docx",
            "version": current["version"],
        },
    )
    assert blocked.status_code == 422
    assert blocked.json()["code"] == "export_blocked"
    codes = {item["code"] for item in blocked.json()["details"]["qa"]["blockers"]}
    assert "unconfirmed_sections" in codes
    review = client.post(
        f"/api/v1/projects/{project['id']}/exports",
        json={
            "snapshot_id": snapshot["id"],
            "export_kind": "review",
            "format": "docx",
            "version": current["version"],
        },
    )
    assert review.status_code == 202, review.text
    assert review.json()["status"] == "succeeded"
    assert review.json()["qa_json"]["stats"]["unconfirmed_sections"] == len(workspace["sections"])


def test_candidates_diff_selection_and_optimistic_lock(client, project):
    _, workspace = upload_and_parse(client, project)
    section = next(item for item in workspace["sections"] if "技术方案" in item["title"])
    candidates = client.get(f"/api/v1/sections/{section['id']}/candidates")
    assert candidates.status_code == 200
    asset_candidate = next(item for item in candidates.json() if item["candidate_type"] == "asset")
    diff = client.get(
        f"/api/v1/sections/{section['id']}/diff", params={"candidate_id": asset_candidate["id"]}
    )
    assert diff.status_code == 200
    assert diff.json()["diff"]["changed"] is True
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    stale = client.post(
        f"/api/v1/sections/{section['id']}:select-version",
        json={"candidate_id": asset_candidate["id"], "version": current["version"] - 1},
    )
    assert stale.status_code == 409
    selected = client.post(
        f"/api/v1/sections/{section['id']}:select-version",
        json={"candidate_id": asset_candidate["id"], "version": current["version"]},
    )
    assert selected.status_code == 200, selected.text
    assert selected.json()["section"]["review_status"] == "unconfirmed"
    assert (
        selected.json()["revision"]["source_asset_revision_id"] == asset_candidate["candidate_id"]
    )


def test_review_snapshot_is_immutable_during_later_edits(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    old_revision = client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "paragraph", "text": "快照内旧文本"}],
            "version": current["version"],
        },
    )
    assert old_revision.status_code == 201, old_revision.text
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    snapshot = client.post(
        f"/api/v1/projects/{project['id']}/snapshots", json={"version": current["version"]}
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    client.post(
        f"/api/v1/sections/{section['id']}/revisions",
        json={
            "content_json": [{"type": "paragraph", "text": "快照后新文本"}],
            "version": current["version"],
        },
    )
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
    text = "\n".join(
        paragraph.text for paragraph in Document(io.BytesIO(download.content)).paragraphs
    )
    assert "快照内旧文本" in text
    assert "快照后新文本" not in text


def test_project_rbac_and_locked_section(client, project):
    _, workspace = upload_and_parse(client, project)
    section = workspace["sections"][0]
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    locked = client.post(
        f"/api/v1/sections/{section['id']}:move",
        json={"parent_id": None, "position": 1, "version": current["version"]},
    )
    assert locked.status_code == 400
    assert locked.json()["code"] == "section_locked"
    viewer = client.post(
        "/api/v1/users",
        json={
            "username": "viewer",
            "password": "ViewerPassword!123",
            "display_name": "只读用户",
            "global_role": "viewer",
        },
    ).json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    membership = client.post(
        f"/api/v1/projects/{project['id']}/members",
        json={"user_id": viewer["id"], "project_role": "viewer", "version": current["version"]},
    )
    assert membership.status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login", json={"username": "viewer", "password": "ViewerPassword!123"}
        ).status_code
        == 200
    )
    assert client.get(f"/api/v1/projects/{project['id']}/workspace").status_code == 200
    forbidden = client.post(
        f"/api/v1/sections/{section['id']}/revisions", json={"content_json": [], "version": 1}
    )
    assert forbidden.status_code == 403
    other = client.get(f"/api/v1/projects/{project['id']}/requirements")
    assert other.status_code == 200
