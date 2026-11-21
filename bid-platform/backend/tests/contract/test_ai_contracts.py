from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.section import ProjectSection
from app.models.task import AIRun
from app.models.tender import Requirement, TenderDocument
from tests.helpers import upload_and_parse


class FakeGateway:
    calls = []
    mode = "valid"

    def complete(self, *, system_prompt, input_payload):
        type(self).calls.append(system_prompt)
        if "信息提取器" in system_prompt:
            if self.mode == "schema_invalid":
                return {"requirements": [{"category": "technical"}]}, {}, 1
            block = next(
                block for block in input_payload["blocks"] if block["text"] == "按实际方案填写"
            )
            anchor = "fake:anchor" if self.mode == "invalid_anchor" else block["anchor_key"]
            requirement = {
                "category": "technical",
                "response_type": "respond",
                "text": "按实际方案填写",
                "quote": "按实际方案填写",
                "anchor_keys": [anchor],
                "status": "original",
                "confidence": 0.98,
                "mandatory_level": "mandatory",
                "score_max": None,
                "normalized": {"package": None},
            }
            return {"requirements": [requirement]}, {"total_tokens": 100}, 1
        if "风险与策略分析器" in system_prompt:
            redline = input_payload["redlines"][0]["id"]
            anchor = input_payload["requirements"][0]["anchor_keys"][0]
            risk = {
                "requirement_code": "REQ-001",
                "redline_rule_id": redline,
                "category": "付款方式",
                "conflict_type": "ambiguous",
                "severity": "medium",
                "recommendation": "书面澄清",
                "legal_review": False,
                "anchor_keys": [anchor],
            }
            strategy = {
                "go_no_go": "conditional",
                "preconditions": ["完成澄清"],
                "negotiable": ["付款"],
                "non_negotiable": [],
                "clarification_questions": ["付款节点？"],
            }
            return (
                {"risks": [risk], "score_assessments": [], "strategy": strategy},
                {"total_tokens": 80},
                1,
            )
        node = input_payload["nodes"][0]
        return (
            {
                "mappings": [
                    {
                        "source_node_id": node["source_node_id"],
                        "action": "map",
                        "target_node_id": node["allowed_target_node_ids"][0],
                        "confidence": 0.95,
                        "reason": "同义编排",
                    }
                ]
            },
            {},
            1,
        )


def test_ai_two_regular_calls_and_optional_third_mapping(client, project, monkeypatch):
    FakeGateway.calls = []
    FakeGateway.mode = "valid"
    monkeypatch.setattr("app.services.ai.tasks.AIGateway", FakeGateway)
    _, before = upload_and_parse(client, project)
    before_content = {
        section["id"]: section["selected_revision"]["content_json"]
        for section in before["sections"]
    }
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    analyzed = client.post(
        f"/api/v1/projects/{project['id']}:analyze", json={"version": current["version"]}
    )
    assert analyzed.status_code == 202
    assert analyzed.json()["status"] == "succeeded", analyzed.json()
    assert analyzed.json()["result_json"]["status"] == "succeeded"
    assert len(FakeGateway.calls) == 2
    requirements = client.get(f"/api/v1/projects/{project['id']}/requirements").json()
    assert len(requirements) == 1
    assert requirements[0]["anchors"][0]["quote"] == "按实际方案填写"
    risks = client.get(f"/api/v1/projects/{project['id']}/risks").json()
    assert len(risks) == 1 and risks[0]["disposition"] == "pending"
    after = client.get(f"/api/v1/projects/{project['id']}/workspace").json()
    assert before_content == {
        section["id"]: section["selected_revision"]["content_json"] for section in after["sections"]
    }

    with SessionLocal() as db:
        group = ProjectSection(
            project_id=project["id"],
            parent_id=None,
            position=10,
            title="编排分组",
            section_key="编排分组",
            source_type="user_only",
            content_mode="group",
        )
        db.add(group)
        section = db.get(ProjectSection, after["sections"][0]["id"])
        section.source_type = "user_only"
        section.locked = False
        section.mapping_status = "needs_review"
        db.commit()
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    mapped = client.post(
        f"/api/v1/projects/{project['id']}:resolve-mapping", json={"version": current["version"]}
    )
    assert mapped.status_code == 202
    assert mapped.json()["result_json"]["status"] == "succeeded", mapped.json()
    assert len(FakeGateway.calls) == 3

    current = client.get(f"/api/v1/projects/{project['id']}").json()
    repeated = client.post(
        f"/api/v1/projects/{project['id']}:analyze", json={"version": current["version"]}
    )
    assert repeated.json()["result_json"]["status"] == "succeeded"
    assert len(FakeGateway.calls) == 3
    with SessionLocal() as db:
        runs = db.scalars(select(AIRun).where(AIRun.project_id == project["id"])).all()
        assert {run.task_type for run in runs} == {"extraction", "risk", "mapping"}


def test_fake_anchor_is_rejected_without_risk_call_or_requirement(client, project, monkeypatch):
    FakeGateway.calls = []
    FakeGateway.mode = "invalid_anchor"
    monkeypatch.setattr("app.services.ai.tasks.AIGateway", FakeGateway)
    upload_and_parse(client, project)
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    result = client.post(
        f"/api/v1/projects/{project['id']}:analyze", json={"version": current["version"]}
    ).json()
    assert result["result_json"]["status"] == "needs_review"
    assert len(FakeGateway.calls) == 1
    assert client.get(f"/api/v1/projects/{project['id']}/requirements").json() == []
    assert client.get(f"/api/v1/projects/{project['id']}/risks").json() == []


def test_schema_failure_has_no_semantic_retry(client, project, monkeypatch):
    FakeGateway.calls = []
    FakeGateway.mode = "schema_invalid"
    monkeypatch.setattr("app.services.ai.tasks.AIGateway", FakeGateway)
    upload_and_parse(client, project)
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    result = client.post(
        f"/api/v1/projects/{project['id']}:analyze", json={"version": current["version"]}
    ).json()
    assert result["result_json"]["status"] == "needs_review"
    assert len(FakeGateway.calls) == 1
    with SessionLocal() as db:
        run = db.scalar(select(AIRun).where(AIRun.project_id == project["id"]))
        assert run.status == "needs_review"
        assert run.error_code == "invalid_ai_output"
        document_ids = db.scalars(
            select(TenderDocument.id).where(TenderDocument.project_id == project["id"])
        ).all()
        assert (
            db.scalar(select(Requirement).where(Requirement.document_id.in_(document_ids))) is None
        )


def test_ai_disabled_does_not_block_workspace(client, project):
    _, workspace = upload_and_parse(client, project)
    current = client.get(f"/api/v1/projects/{project['id']}").json()
    result = client.post(
        f"/api/v1/projects/{project['id']}:analyze", json={"version": current["version"]}
    ).json()
    assert result["status"] == "failed"
    assert result["error_code"] == "ai_disabled"
    assert client.get(f"/api/v1/projects/{project['id']}/workspace").json()["sections"]
