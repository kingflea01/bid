import json
from difflib import SequenceMatcher
from typing import Any


def _canonical(block: dict[str, Any]) -> str:
    return json.dumps(block, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def structured_diff(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> dict[str, Any]:
    left = [_canonical(block) for block in before]
    right = [_canonical(block) for block in after]
    operations = []
    for tag, i1, i2, j1, j2 in SequenceMatcher(a=left, b=right, autojunk=False).get_opcodes():
        if tag == "equal":
            operations.append(
                {"op": "equal", "before_indices": [i1, i2], "after_indices": [j1, j2]}
            )
        else:
            operations.append(
                {
                    "op": tag,
                    "before_indices": [i1, i2],
                    "after_indices": [j1, j2],
                    "before": before[i1:i2],
                    "after": after[j1:j2],
                }
            )
    return {
        "changed": before != after,
        "before_count": len(before),
        "after_count": len(after),
        "added_blocks": sum(
            max(0, op["after_indices"][1] - op["after_indices"][0])
            for op in operations
            if op["op"] in {"insert", "replace"}
        ),
        "removed_blocks": sum(
            max(0, op["before_indices"][1] - op["before_indices"][0])
            for op in operations
            if op["op"] in {"delete", "replace"}
        ),
        "operations": operations,
    }
