import copy
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.project import Activity, Job, Project, ProjectConfigRef
from app.models.risk import Risk, ScoreAssessment
from app.models.section import (
    ProjectFact,
    ProjectSectionRevision,
    ProjectSnapshot,
    SectionRequirement,
)
from app.models.task import ExportTask
from app.models.tender import Requirement, RequirementAnchor
from app.models.user import User
from app.services.persistence import model_dict
from app.services.workspace.qa import evaluate_snapshot_qa

SOURCE_LABELS = {
    "tender": "招标原始格式",
    "template": "已发布模板",
    "asset": "已发布素材",
    "history": "历史项目确认版本",
    "manual": "当前项目人工修订",
}


def job_dict(job: Job) -> dict[str, Any]:
    return {**model_dict(job), "task_type": job.kind}


def project_dict(db: Session, project: Project) -> dict[str, Any]:
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    return {
        **model_dict(project),
        "package_name": project.package,
        "config_refs": model_dict(refs) if refs else None,
    }


def frontend_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = copy.deepcopy(blocks)
    for block in result:
        kind = block.get("type")
        if kind == "attachment_ref":
            file_id = block.get("file_id") or block.get("attachment_id")
            label = block.get("label") or block.get("name")
            block["file_id"] = file_id
            block["attachment_id"] = file_id
            block["name"] = label
            block["label"] = label
        elif kind == "placeholder":
            label = block.get("label") or block.get("name") or block.get("text", "").strip("[]")
            block["label"] = label
            block.setdefault("name", label)
            block.setdefault("text", f"[[{label}]]")
            block.setdefault("placeholder_type", block.get("kind"))
        elif kind == "tender_ooxml_ref":
            block.setdefault("label", block.get("text") or block.get("anchor_key"))
    return result


def revision_dict(revision: ProjectSectionRevision | None) -> dict[str, Any] | None:
    if revision is None:
        return None
    return {
        **model_dict(revision),
        "content_json": frontend_blocks(revision.content_json),
        "source_label": SOURCE_LABELS.get(revision.source_type, revision.source_type),
    }


def fact_dict(fact: ProjectFact, project_version: int) -> dict[str, Any]:
    return {**model_dict(fact), "version": project_version}


def requirement_dict(db: Session, requirement: Requirement) -> dict[str, Any]:
    anchors = db.scalars(
        select(RequirementAnchor).where(RequirementAnchor.requirement_id == requirement.id)
    ).all()
    mappings = db.scalars(
        select(SectionRequirement).where(SectionRequirement.requirement_id == requirement.id)
    ).all()
    if not mappings:
        mapping_status = "missing"
        mapping_source = None
    else:
        confirmed = [mapping for mapping in mappings if mapping.mapping_status == "confirmed"]
        mapping_status = (
            "confirmed"
            if len(confirmed) == len(mappings)
            else "partial"
            if confirmed
            else "unconfirmed"
        )
        mapping_source = mappings[0].mapping_source
    return {
        **model_dict(requirement),
        "anchors": [{"anchor_key": anchor.anchor_key, "quote": anchor.quote} for anchor in anchors],
        "section_id": mappings[0].section_id if mappings else None,
        "mapping_status": mapping_status,
        "mapping_source": mapping_source,
    }


def risk_dict(db: Session, risk: Risk) -> dict[str, Any]:
    requirement = db.get(Requirement, risk.requirement_id) if risk.requirement_id else None
    return {**model_dict(risk), "requirement_text": requirement.text if requirement else None}


def score_dict(db: Session, score: ScoreAssessment) -> dict[str, Any]:
    requirement = db.get(Requirement, score.requirement_id)
    return {**model_dict(score), "requirement_text": requirement.text if requirement else None}


def activity_dict(db: Session, activity: Activity) -> dict[str, Any]:
    actor = db.get(User, activity.actor_id) if activity.actor_id else None
    section_id = activity.detail_json.get("section_id")
    if not section_id and activity.entity_type == "section":
        section_id = activity.entity_id
    return {
        **model_dict(activity),
        "actor_name": actor.display_name if actor else None,
        "section_id": section_id,
    }


def snapshot_dict(db: Session, snapshot: ProjectSnapshot) -> dict[str, Any]:
    project = db.get(Project, snapshot.project_id)
    creator = db.get(User, snapshot.created_by)
    qa = evaluate_snapshot_qa(db, project, snapshot, "formal")
    return {
        **model_dict(snapshot),
        "created_by_name": creator.display_name if creator else None,
        "formal_ready": qa["passed"],
        "qa_json": {"passed": qa["passed"], "blockers": qa["blockers"], "stats": qa["stats"]},
    }


def export_dict(db: Session, task: ExportTask) -> dict[str, Any]:
    snapshot = db.get(ProjectSnapshot, task.snapshot_id)
    return {**model_dict(task), "snapshot_no": snapshot.snapshot_no if snapshot else None}


def export_readiness(db: Session, project: Project) -> dict[str, Any]:
    latest = db.scalar(
        select(ProjectSnapshot)
        .where(ProjectSnapshot.project_id == project.id)
        .order_by(ProjectSnapshot.snapshot_no.desc())
        .limit(1)
    )
    if latest is None:
        return {
            "can_export_review": True,
            "can_export_formal": False,
            "checks": [
                {
                    "key": "snapshot",
                    "label": "已保存项目快照",
                    "passed": False,
                    "blocking": True,
                    "detail": "请先保存快照",
                }
            ],
            "unconfirmed_sections": 0,
            "open_blocking_gaps": 0,
            "undisposed_risks": 0,
            "current_snapshot_id": None,
        }
    qa = evaluate_snapshot_qa(db, project, latest, "formal")
    blockers = {blocker["code"]: blocker for blocker in qa["blockers"]}
    stats = qa["stats"]

    def check(key: str, label: str, code: str, passed_detail: str) -> dict[str, Any]:
        blocker = blockers.get(code)
        count = len(blocker["entities"]) if blocker else 0
        return {
            "key": key,
            "label": label,
            "passed": blocker is None,
            "blocking": True,
            "detail": blocker["message"] if blocker else passed_detail,
            **({"count": count} if blocker else {}),
        }

    checks = [
        {
            "key": "snapshot",
            "label": "已保存不可变快照",
            "passed": True,
            "blocking": True,
            "detail": f"快照 V{latest.snapshot_no}",
        },
        check("sections", "内容章节已确认", "unconfirmed_sections", "全部内容章节已确认"),
        check("gaps", "阻塞缺口已关闭", "open_blocking_gaps", "无阻塞缺口"),
        check("risks", "风险已完成人工处置", "pending_risks", "风险均已处置"),
        check("placeholders", "字段与附件占位符已补齐", "placeholders", "无未解释占位符"),
        check("facts", "统一事实已确认", "unconfirmed_facts", "事实字段状态一致"),
        check("assets", "素材与附件均在有效期内", "expired_assets", "素材与附件有效"),
        check("formats", "必要招标格式块完整", "tender_format_missing", "招标格式块完整"),
        check("parse", "招标解析已确认", "parse_not_confirmed", "解析状态已确认"),
        check("snapshot_current", "快照与当前确认状态一致", "snapshot_stale", "快照状态一致"),
    ]
    return {
        "can_export_review": True,
        "can_export_formal": qa["passed"],
        "checks": checks,
        "unconfirmed_sections": stats["unconfirmed_sections"],
        "open_blocking_gaps": stats["open_blocking_gaps"],
        "undisposed_risks": stats["pending_risks"],
        "current_snapshot_id": latest.id,
    }
