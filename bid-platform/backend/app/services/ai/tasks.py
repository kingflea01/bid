import copy
import hashlib
import json
import math
import re
import time
from pathlib import Path
from typing import Any

from jsonschema import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import utcnow
from app.core.errors import AppError, bad_request
from app.models.config import CompanyRevision, ProductRevision, RedlineRule
from app.models.project import Job, Project, ProjectConfigRef
from app.models.risk import Risk, ScoreAssessment
from app.models.section import ProjectSection, SectionRequirement
from app.models.task import AIRun
from app.models.tender import Requirement, RequirementAnchor, TenderBlock, TenderDocument
from app.services.ai.cache import cached_run, input_hash
from app.services.ai.gateway import AIGateway
from app.services.ai.schemas import EXTRACTION_SCHEMA, MAPPING_SCHEMA, RISK_SCHEMA, validate_schema
from app.services.audit import record_activity
from app.services.documents.anchors import validate_anchor_quote
from app.services.structure.rules import titles_match
from app.services.workspace.state import touch_project

SCHEMA_VERSION = "v1"


def _prompt(name: str) -> str:
    return (Path(__file__).parent / "prompts" / f"{name}.txt").read_text(encoding="utf-8")


def _config_manifest(db: Session, project: Project) -> dict[str, Any]:
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    return {
        "company_revision_id": refs.company_revision_id,
        "product_revision_id": refs.product_revision_id,
        "template_revision_id": refs.template_revision_id,
        "redline_rule_ids": sorted(refs.redline_rule_ids_json),
    }


def _documents(db: Session, project: Project) -> list[TenderDocument]:
    return db.scalars(
        select(TenderDocument)
        .where(TenderDocument.project_id == project.id, TenderDocument.status == "parsed")
        .order_by(TenderDocument.created_at)
    ).all()


def _blocks(db: Session, project: Project) -> list[TenderBlock]:
    documents = _documents(db, project)
    if not documents:
        return []
    return db.scalars(
        select(TenderBlock)
        .where(TenderBlock.document_id.in_([doc.id for doc in documents]))
        .order_by(TenderBlock.document_id, TenderBlock.order_no)
    ).all()


def _base_manifest(db: Session, project: Project) -> dict[str, Any]:
    documents = _documents(db, project)
    if not documents:
        raise bad_request("请先成功解析招标文档", code="document_required")
    return {
        "files": [
            {"sha256": doc.sha256, "parser_version": doc.parser_version} for doc in documents
        ],
        "package": project.package,
        "procurement_type": project.procurement_type,
        "schema_version": SCHEMA_VERSION,
        "prompt_version": get_settings().ai_prompt_version,
        "model": get_settings().ai_model,
        **_config_manifest(db, project),
    }


def _output_digest(output: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(output, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def _latest_project_run(db: Session, project_id: str, task_type: str) -> AIRun | None:
    return db.scalar(
        select(AIRun)
        .where(AIRun.project_id == project_id, AIRun.task_type == task_type)
        .order_by(AIRun.created_at.desc())
        .limit(1)
    )


def _execute(
    db: Session,
    project: Project,
    job: Job,
    task_type: str,
    manifest: dict[str, Any],
    prompt_name: str,
    payload: dict[str, Any],
    schema: dict[str, Any],
) -> AIRun:
    latest = _latest_project_run(db, project.id, task_type)
    if latest is not None:
        return latest
    digest = input_hash(task_type, manifest)
    cached = cached_run(db, task_type, digest)
    if cached:
        run = AIRun(
            project_id=project.id,
            job_id=job.id,
            task_type=task_type,
            input_hash=digest,
            prompt_version=get_settings().ai_prompt_version,
            model=get_settings().ai_model,
            status="succeeded",
            attempts=0,
            input_manifest_json=manifest,
            output_json=copy.deepcopy(cached.output_json),
            token_usage={"cache_hit": True, "source_run_id": cached.id},
            started_at=utcnow(),
            finished_at=utcnow(),
        )
        db.add(run)
        db.flush()
        return run
    run = AIRun(
        project_id=project.id,
        job_id=job.id,
        task_type=task_type,
        input_hash=digest,
        prompt_version=get_settings().ai_prompt_version,
        model=get_settings().ai_model,
        status="running",
        input_manifest_json=manifest,
        started_at=utcnow(),
    )
    db.add(run)
    db.flush()
    stopwatch = time.perf_counter()
    try:
        output, usage, attempts = AIGateway().complete(
            system_prompt=_prompt(prompt_name), input_payload=payload
        )
        run.attempts = attempts
        run.output_json = output
        run.token_usage = usage if isinstance(usage, dict) else {}
        validate_schema(output, schema)
        run.status = "succeeded"
    except AppError as exc:
        run.status = "needs_review" if exc.code == "invalid_ai_output" else "failed"
        run.error_code = exc.code
        run.finished_at = utcnow()
        run.duration_ms = (time.perf_counter() - stopwatch) * 1000
        db.commit()
        if run.status == "failed":
            raise
        return run
    except (ValidationError, ValueError, TypeError):
        run.status = "needs_review"
        run.error_code = "invalid_ai_output"
        run.finished_at = utcnow()
        run.duration_ms = (time.perf_counter() - stopwatch) * 1000
        db.commit()
        return run
    run.finished_at = utcnow()
    run.duration_ms = (time.perf_counter() - stopwatch) * 1000
    db.flush()
    return run


def _mark_invalid(db: Session, run: AIRun, code: str = "invalid_ai_output") -> AIRun:
    run.status = "needs_review"
    run.error_code = code
    run.finished_at = utcnow()
    db.commit()
    return run


def _finite(value: Any) -> bool:
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, dict):
        return all(_finite(child) for child in value.values())
    if isinstance(value, list):
        return all(_finite(child) for child in value)
    return True


def _validate_extraction(
    output: dict[str, Any], blocks: list[TenderBlock], package: str | None
) -> None:
    if not _finite(output):
        raise ValueError("non-finite number")
    block_map = {block.anchor_key: block for block in blocks}
    for item in output["requirements"]:
        anchors = item["anchor_keys"]
        if any(anchor not in block_map for anchor in anchors):
            raise ValueError("unknown anchor")
        if item["status"] == "missing":
            if anchors or item["quote"]:
                raise ValueError("missing item has evidence")
            continue
        if not anchors or not item["quote"]:
            raise ValueError("requirement has no source")
        if not any(validate_anchor_quote(block_map[anchor], item["quote"]) for anchor in anchors):
            raise ValueError("quote does not match anchor")
        normalized_package = item["normalized"].get("package")
        if package and item["category"] == "technical":
            if normalized_package and str(normalized_package) != str(package):
                raise ValueError("outside target package")
            evidence = " ".join(block_map[anchor].text for anchor in anchors)
            package_numbers = set(
                re.findall(r"(?:第\s*(\d+)\s*(?:分包|包)|包号\s*[：:]?\s*(\d+))", evidence)
            )
            flattened = {number for pair in package_numbers for number in pair if number}
            if flattened and str(package) not in flattened:
                raise ValueError("outside target package")


def _persist_requirements(
    db: Session, project: Project, output: dict[str, Any]
) -> list[Requirement]:
    documents = _documents(db, project)
    document_by_anchor = {block.anchor_key: block.document_id for block in _blocks(db, project)}
    persisted = []
    for index, item in enumerate(output["requirements"], 1):
        if item["status"] == "missing":
            continue
        code = f"REQ-{index:03d}"
        document_id = document_by_anchor[item["anchor_keys"][0]]
        requirement = db.scalar(
            select(Requirement).where(
                Requirement.code == code, Requirement.document_id.in_([doc.id for doc in documents])
            )
        )
        if requirement is None:
            requirement = Requirement(
                document_id=document_id,
                code=code,
                category=item["category"],
                response_type=item["response_type"],
                text=item["text"],
                normalized_json=item["normalized"],
                mandatory_level=item["mandatory_level"],
                score_max=item["score_max"],
                status="original" if item["status"] == "original" else "needs_review",
                confidence=item["confidence"],
            )
            db.add(requirement)
            db.flush()
        else:
            requirement.document_id = document_id
            requirement.category = item["category"]
            requirement.response_type = item["response_type"]
            requirement.text = item["text"]
            requirement.normalized_json = item["normalized"]
            requirement.mandatory_level = item["mandatory_level"]
            requirement.score_max = item["score_max"]
            requirement.status = "original" if item["status"] == "original" else "needs_review"
            requirement.confidence = item["confidence"]
        existing_anchors = db.scalars(
            select(RequirementAnchor).where(RequirementAnchor.requirement_id == requirement.id)
        ).all()
        for anchor in existing_anchors:
            db.delete(anchor)
        db.flush()
        for anchor_key in item["anchor_keys"]:
            db.add(
                RequirementAnchor(
                    requirement_id=requirement.id, anchor_key=anchor_key, quote=item["quote"]
                )
            )
        persisted.append(requirement)
    db.flush()
    _map_requirements(db, project, persisted)
    return persisted


def _map_requirements(db: Session, project: Project, requirements: list[Requirement]) -> None:
    sections = db.scalars(
        select(ProjectSection).where(ProjectSection.project_id == project.id)
    ).all()
    category_terms = {
        "qualification": ("资格", "商务", "证明"),
        "technical": ("技术", "方案", "需求"),
        "commercial": ("商务", "售后", "服务"),
        "contract": ("合同", "商务", "承诺"),
        "response_format": ("格式", "附件", "响应"),
        "attachments": ("附件", "其他材料", "证明"),
        "material": ("承诺", "偏差", "响应"),
        "invalidation": ("资格", "响应函"),
    }
    for requirement in requirements:
        terms = category_terms.get(requirement.category, ())
        anchor_keys = set(
            db.scalars(
                select(RequirementAnchor.anchor_key).where(
                    RequirementAnchor.requirement_id == requirement.id
                )
            ).all()
        )
        target = next(
            (
                section
                for section in sections
                if section.source_anchor and section.source_anchor in anchor_keys
            ),
            None,
        )
        if target is None:
            target = next(
                (section for section in sections if any(term in section.title for term in terms)),
                None,
            )
        if target is None:
            continue
        mapping = db.get(
            SectionRequirement, {"section_id": target.id, "requirement_id": requirement.id}
        )
        if mapping is None:
            db.add(
                SectionRequirement(
                    section_id=target.id,
                    requirement_id=requirement.id,
                    mapping_source="deterministic",
                    mapping_status="suggested",
                )
            )


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    sensitive = re.compile(
        r"password|secret|token|key|bank|account|idcard|phone|mobile|email|密码|密钥|银行|账号|身份证|手机|邮箱",
        re.I,
    )
    return {key: value for key, value in fields.items() if not sensitive.search(key)}


def _risk_payload(
    db: Session, project: Project, requirements: list[Requirement], extraction: AIRun
) -> tuple[dict[str, Any], dict[str, Any]]:
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    company = db.get(CompanyRevision, refs.company_revision_id)
    product = db.get(ProductRevision, refs.product_revision_id)
    redlines = [db.get(RedlineRule, rule_id) for rule_id in refs.redline_rule_ids_json]
    manifest = {
        **_base_manifest(db, project),
        "extraction_hash": extraction.input_hash,
        "extraction_output": _output_digest(extraction.output_json),
    }
    payload = {
        "requirements": [
            {
                "code": req.code,
                "category": req.category,
                "text": req.text,
                "normalized": req.normalized_json,
                "mandatory_level": req.mandatory_level,
                "score_max": req.score_max,
                "anchor_keys": [
                    anchor.anchor_key
                    for anchor in db.scalars(
                        select(RequirementAnchor).where(RequirementAnchor.requirement_id == req.id)
                    ).all()
                ],
            }
            for req in requirements
        ],
        "redlines": [
            {
                "id": rule.id,
                "category": rule.category,
                "position": rule.position,
                "condition": rule.condition_json,
                "action": rule.action,
                "legal_review": rule.legal_review,
            }
            for rule in redlines
            if rule
        ],
        "deterministic_qa": [
            {"document_id": doc.id, "checks": doc.parse_qa_json.get("checks", [])}
            for doc in _documents(db, project)
        ],
        "company_fields": _safe_fields(company.fields_json),
        "product_fields": _safe_fields(product.fields_json),
        "technical_fields": _safe_fields(product.technical_fields_json),
        "anchors": [
            {"anchor_key": block.anchor_key, "text": block.text}
            for block in _blocks(db, project)
            if any(
                anchor.anchor_key == block.anchor_key
                for req in requirements
                for anchor in db.scalars(
                    select(RequirementAnchor).where(RequirementAnchor.requirement_id == req.id)
                ).all()
            )
        ],
    }
    return payload, manifest


def _validate_risk(
    output: dict[str, Any],
    requirements: list[Requirement],
    allowed_redlines: set[str],
    blocks: list[TenderBlock],
) -> None:
    if not _finite(output):
        raise ValueError("non-finite number")
    req_map = {req.code: req for req in requirements}
    anchor_keys = {block.anchor_key for block in blocks}
    for risk in output["risks"]:
        if risk["requirement_code"] and risk["requirement_code"] not in req_map:
            raise ValueError("unknown requirement")
        if not risk["requirement_code"] and not risk["anchor_keys"]:
            raise ValueError("unlinked risk")
        if risk["redline_rule_id"] and risk["redline_rule_id"] not in allowed_redlines:
            raise ValueError("unknown redline")
        if any(anchor not in anchor_keys for anchor in risk["anchor_keys"]):
            raise ValueError("unknown anchor")
    for score in output["score_assessments"]:
        requirement = req_map.get(score["requirement_code"])
        if requirement is None or requirement.category != "scoring":
            raise ValueError("invalid scoring requirement")
        if (
            "价格" in requirement.text
            or "报价" in requirement.text
            or requirement.normalized_json.get("score_type") == "price"
        ):
            raise ValueError("price scoring forbidden")
        low, high = score["score_min"], score["score_max"]
        if (
            (low is None) != (high is None)
            or low is not None
            and (low > high or requirement.score_max is not None and high > requirement.score_max)
        ):
            raise ValueError("invalid score interval")


def _persist_risk(
    db: Session, project: Project, output: dict[str, Any], requirements: list[Requirement]
) -> None:
    req_map = {req.code: req for req in requirements}
    for item in output["risks"]:
        requirement_id = req_map[item["requirement_code"]].id if item["requirement_code"] else None
        existing = db.scalar(
            select(Risk).where(
                Risk.project_id == project.id,
                Risk.requirement_id == requirement_id,
                Risk.redline_rule_id == item["redline_rule_id"],
                Risk.category == item["category"],
            )
        )
        if existing and existing.disposition != "pending":
            continue
        values = {
            "requirement_id": requirement_id,
            "redline_rule_id": item["redline_rule_id"],
            "category": item["category"],
            "conflict_type": item["conflict_type"],
            "severity": item["severity"],
            "recommendation": item["recommendation"],
            "legal_review": item["legal_review"],
            "anchors_json": [{"anchor_key": key} for key in item["anchor_keys"]],
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(Risk(project_id=project.id, **values))
    for item in output["score_assessments"]:
        requirement_id = req_map[item["requirement_code"]].id
        existing = db.scalar(
            select(ScoreAssessment).where(
                ScoreAssessment.project_id == project.id,
                ScoreAssessment.requirement_id == requirement_id,
            )
        )
        values = {
            "score_min": item["score_min"],
            "score_max": item["score_max"],
            "evidence_json": item["evidence"],
            "gap_json": item["gaps"],
            "status": "estimated" if item["score_min"] is not None else "unmeasurable",
        }
        if existing:
            for key, value in values.items():
                setattr(existing, key, value)
        else:
            db.add(ScoreAssessment(project_id=project.id, requirement_id=requirement_id, **values))


def run_analysis(db: Session, job: Job) -> dict[str, Any]:
    project = db.get(Project, job.project_id)
    blocks = _blocks(db, project)
    manifest = _base_manifest(db, project)
    payload = {
        "package": project.package,
        "procurement_type": project.procurement_type,
        "blocks": [
            {"anchor_key": block.anchor_key, "text": block.text, "page_no": block.page_no}
            for block in blocks
        ],
        "schema_version": SCHEMA_VERSION,
    }
    extraction = _execute(
        db, project, job, "extraction", manifest, "extract", payload, EXTRACTION_SCHEMA
    )
    if extraction.status != "succeeded":
        return {
            "status": extraction.status,
            "extraction_run_id": extraction.id,
            "error_code": extraction.error_code,
        }
    try:
        _validate_extraction(extraction.output_json, blocks, project.package)
    except ValueError:
        _mark_invalid(db, extraction)
        return {
            "status": "needs_review",
            "extraction_run_id": extraction.id,
            "error_code": extraction.error_code,
        }
    requirements = _persist_requirements(db, project, extraction.output_json)
    risk_payload, risk_manifest = _risk_payload(db, project, requirements, extraction)
    risk = _execute(db, project, job, "risk", risk_manifest, "risk", risk_payload, RISK_SCHEMA)
    if risk.status != "succeeded":
        db.commit()
        return {
            "status": risk.status,
            "extraction_run_id": extraction.id,
            "risk_run_id": risk.id,
            "error_code": risk.error_code,
        }
    refs = db.scalar(select(ProjectConfigRef).where(ProjectConfigRef.project_id == project.id))
    try:
        _validate_risk(risk.output_json, requirements, set(refs.redline_rule_ids_json), blocks)
    except ValueError:
        _mark_invalid(db, risk)
        return {
            "status": "needs_review",
            "extraction_run_id": extraction.id,
            "risk_run_id": risk.id,
            "error_code": risk.error_code,
        }
    _persist_risk(db, project, risk.output_json, requirements)
    touch_project(db, project)
    record_activity(
        db,
        None,
        "project.analyzed",
        "project",
        project.id,
        project.id,
        {
            "extraction_run_id": extraction.id,
            "risk_run_id": risk.id,
            "requirements": len(requirements),
        },
    )
    db.commit()
    return {
        "status": "succeeded",
        "extraction_run_id": extraction.id,
        "risk_run_id": risk.id,
        "requirements": len(requirements),
        "strategy": risk.output_json["strategy"],
    }


def run_mapping(db: Session, job: Job) -> dict[str, Any]:
    project = db.get(Project, job.project_id)
    sections = db.scalars(
        select(ProjectSection).where(ProjectSection.project_id == project.id)
    ).all()
    unresolved = [section for section in sections if section.mapping_status == "needs_review"]
    if not unresolved:
        return {"status": "succeeded", "mappings": []}
    section_map = {section.id: section for section in sections}

    def is_descendant(candidate: ProjectSection, section: ProjectSection) -> bool:
        cursor = candidate
        while cursor.parent_id:
            if cursor.parent_id == section.id:
                return True
            cursor = section_map[cursor.parent_id]
        return False

    nodes = []
    for section in unresolved:
        allowed = [
            candidate.id
            for candidate in sections
            if candidate.id != section.id
            and not is_descendant(candidate, section)
            and (candidate.content_mode == "group" or titles_match(candidate.title, section.title))
        ]
        if section.parent_id:
            allowed.append(section.parent_id)
        nodes.append(
            {
                "source_node_id": section.id,
                "title": section.title,
                "current_parent_id": section.parent_id,
                "allowed_target_node_ids": sorted(set(allowed)),
                "allowed_actions": ["map", "append", "omit", "clean", "needs_review"],
                "rule_context": {
                    "source_type": section.source_type,
                    "section_key": section.section_key,
                },
            }
        )
    manifest = {
        **_base_manifest(db, project),
        "nodes": [
            {"id": node["source_node_id"], "targets": node["allowed_target_node_ids"]}
            for node in nodes
        ],
    }
    run = _execute(
        db, project, job, "mapping", manifest, "mapping", {"nodes": nodes}, MAPPING_SCHEMA
    )
    if run.status != "succeeded":
        return {"status": run.status, "mapping_run_id": run.id, "error_code": run.error_code}
    try:
        mappings = run.output_json["mappings"]
        if (
            len(mappings) != len(nodes)
            or {item["source_node_id"] for item in mappings}
            != {node["source_node_id"] for node in nodes}
            or len({item["source_node_id"] for item in mappings}) != len(mappings)
        ):
            raise ValueError("incomplete mapping")
        allowed_map = {
            node["source_node_id"]: set(node["allowed_target_node_ids"]) for node in nodes
        }
        for item in mappings:
            if item["action"] in {"map", "append"}:
                if item["target_node_id"] not in allowed_map[item["source_node_id"]]:
                    raise ValueError("target not allowed")
            elif item["target_node_id"] is not None:
                raise ValueError("unexpected target")
    except ValueError:
        _mark_invalid(db, run, "invalid_ai_mapping")
        return {"status": "needs_review", "mapping_run_id": run.id, "error_code": run.error_code}
    applied = []
    for item in mappings:
        section = section_map[item["source_node_id"]]
        if item["confidence"] < 0.75 or item["action"] == "needs_review":
            continue
        if item["action"] in {"map", "append"}:
            section.parent_id = item["target_node_id"]
            section.position = len(
                [candidate for candidate in sections if candidate.parent_id == section.parent_id]
            )
            section.mapping_status = "resolved"
        elif item["action"] == "omit":
            section.mapping_status = "omitted"
        elif item["action"] == "clean":
            section.title = re.sub(r"^\d+(\.\d+)*[\.、]?\s*", "", section.title).strip()
            section.mapping_status = "resolved"
        section.version += 1
        applied.append(
            {
                "source_node_id": section.id,
                "action": item["action"],
                "target_node_id": item["target_node_id"],
            }
        )
    touch_project(db, project)
    record_activity(
        db,
        None,
        "project.mapping_resolved",
        "project",
        project.id,
        project.id,
        {"mappings": applied, "run_id": run.id},
    )
    db.commit()
    return {"status": "succeeded", "mapping_run_id": run.id, "mappings": applied}
