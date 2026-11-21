from tests.fixtures.documents import tender_docx_bytes


def upload_and_parse(client, project, data: bytes | None = None):
    upload = client.post(
        f"/api/v1/projects/{project['id']}/tender-documents",
        files={
            "file": (
                "tender.docx",
                data or tender_docx_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
        data={"version": str(project["version"])},
    )
    assert upload.status_code == 201, upload.text
    document = upload.json()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    parsed = client.post(
        f"/api/v1/projects/{project['id']}:parse",
        json={"document_id": document["id"], "version": current["version"]},
    )
    assert parsed.status_code == 202, parsed.text
    job = parsed.json()
    assert job["status"] == "succeeded", job
    document["status"] = "parsed"
    workspace = client.get(f"/api/v1/projects/{project['id']}/workspace")
    assert workspace.status_code == 200, workspace.text
    return document, workspace.json()


def confirm_ready_project(client, project_id):
    workspace = client.get(f"/api/v1/projects/{project_id}/workspace").json()
    for section in workspace["sections"]:
        if section["content_mode"] == "group":
            continue
        current = client.get(f"/api/v1/projects/{project_id}").json()
        response = client.post(
            f"/api/v1/sections/{section['id']}:confirm", json={"version": current["version"]}
        )
        assert response.status_code == 200, response.text
    workspace = client.get(f"/api/v1/projects/{project_id}/workspace").json()
    for fact in workspace["facts"]:
        current = client.get(f"/api/v1/projects/{project_id}").json()
        response = client.patch(
            f"/api/v1/projects/{project_id}/facts/{fact['fact_key']}",
            json={
                "value": fact["value_json"],
                "value_type": fact["value_type"],
                "status": "confirmed",
                "version": current["version"],
            },
        )
        assert response.status_code == 200, response.text
    current = client.get(f"/api/v1/projects/{project_id}").json()
    response = client.patch(
        f"/api/v1/projects/{project_id}/facts/落款日期",
        json={
            "value": "2026-11-21",
            "value_type": "date",
            "status": "confirmed",
            "version": current["version"],
        },
    )
    assert response.status_code == 200, response.text
    return client.get(f"/api/v1/projects/{project_id}/workspace").json()
