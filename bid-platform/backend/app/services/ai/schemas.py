from typing import Any

from jsonschema import Draft202012Validator

CATEGORIES = [
    "project",
    "fees",
    "packages",
    "timeline",
    "qualification",
    "scoring",
    "material",
    "technical",
    "commercial",
    "contract",
    "response_format",
    "invalidation",
    "award",
    "attachments",
    "anomalies",
]
ANCHOR = {"type": "string", "minLength": 1, "maxLength": 160}
EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["requirements"],
    "properties": {
        "requirements": {
            "type": "array",
            "maxItems": 1000,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "category",
                    "response_type",
                    "text",
                    "quote",
                    "anchor_keys",
                    "status",
                    "confidence",
                    "mandatory_level",
                    "score_max",
                    "normalized",
                ],
                "properties": {
                    "category": {"enum": CATEGORIES},
                    "response_type": {
                        "enum": ["respond", "evidence", "attachment", "format", "clarify", "record"]
                    },
                    "text": {"type": "string", "minLength": 1, "maxLength": 10000},
                    "quote": {"type": "string", "maxLength": 10000},
                    "anchor_keys": {
                        "type": "array",
                        "maxItems": 20,
                        "uniqueItems": True,
                        "items": ANCHOR,
                    },
                    "status": {"enum": ["original", "inferred", "missing", "needs_review"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "mandatory_level": {"enum": ["normal", "mandatory", "star"]},
                    "score_max": {"type": ["number", "null"], "minimum": 0},
                    "normalized": {"type": "object"},
                },
            },
        }
    },
}
RISK_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["risks", "score_assessments", "strategy"],
    "properties": {
        "risks": {
            "type": "array",
            "maxItems": 500,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "requirement_code",
                    "redline_rule_id",
                    "category",
                    "conflict_type",
                    "severity",
                    "recommendation",
                    "legal_review",
                    "anchor_keys",
                ],
                "properties": {
                    "requirement_code": {"type": ["string", "null"], "maxLength": 80},
                    "redline_rule_id": {"type": ["string", "null"], "maxLength": 36},
                    "category": {"type": "string", "minLength": 1, "maxLength": 100},
                    "conflict_type": {"enum": ["explicit", "ambiguous", "missing"]},
                    "severity": {"enum": ["critical", "high", "medium", "low"]},
                    "recommendation": {"type": "string", "minLength": 1, "maxLength": 4000},
                    "legal_review": {"type": "boolean"},
                    "anchor_keys": {
                        "type": "array",
                        "maxItems": 20,
                        "uniqueItems": True,
                        "items": ANCHOR,
                    },
                },
            },
        },
        "score_assessments": {
            "type": "array",
            "maxItems": 200,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["requirement_code", "score_min", "score_max", "evidence", "gaps"],
                "properties": {
                    "requirement_code": {"type": "string", "maxLength": 80},
                    "score_min": {"type": ["number", "null"], "minimum": 0},
                    "score_max": {"type": ["number", "null"], "minimum": 0},
                    "evidence": {"type": "array", "maxItems": 50, "items": {"type": "object"}},
                    "gaps": {
                        "type": "array",
                        "maxItems": 50,
                        "items": {"type": "string", "maxLength": 1000},
                    },
                },
            },
        },
        "strategy": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "go_no_go",
                "preconditions",
                "negotiable",
                "non_negotiable",
                "clarification_questions",
            ],
            "properties": {
                "go_no_go": {"enum": ["go", "no_go", "conditional", "needs_review"]},
                **{
                    key: {
                        "type": "array",
                        "maxItems": 100,
                        "items": {"type": "string", "maxLength": 2000},
                    }
                    for key in (
                        "preconditions",
                        "negotiable",
                        "non_negotiable",
                        "clarification_questions",
                    )
                },
            },
        },
    },
}
MAPPING_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["mappings"],
    "properties": {
        "mappings": {
            "type": "array",
            "maxItems": 200,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["source_node_id", "action", "target_node_id", "confidence", "reason"],
                "properties": {
                    "source_node_id": {"type": "string", "maxLength": 36},
                    "action": {"enum": ["map", "append", "omit", "clean", "needs_review"]},
                    "target_node_id": {"type": ["string", "null"], "maxLength": 36},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reason": {"type": "string", "maxLength": 1000},
                },
            },
        }
    },
}


def validate_schema(payload: dict[str, Any], schema: dict[str, Any]) -> None:
    Draft202012Validator(schema).validate(payload)
