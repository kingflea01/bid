import copy
from typing import Any

from app.services.structure.rules import AFFINITY, canonical, section_key, titles_match, walk_nodes


def tender_tree(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roots: list[dict[str, Any]] = []
    stack: list[dict[str, Any]] = []
    for item in outline:
        node = {
            "title": item["title"],
            "level": item["level"],
            "source": "tender",
            "locked": True,
            "section_key": section_key(item["title"]),
            "content_mode": "tender_template",
            "source_start_anchor": item.get("source_start_anchor"),
            "source_end_anchor": item.get("source_end_anchor"),
            "content_json": [],
            "children": [],
        }
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots


def normalize_template_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for raw in copy.deepcopy(nodes):
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        content = raw.get("content_json") or []
        if not content and raw.get("content_lines"):
            content = [{"type": "paragraph", "text": str(line)} for line in raw["content_lines"]]
        mode = raw.get("content_mode") or ("fixed_text" if content else "placeholder")
        result.append(
            {
                "title": title,
                "level": int(raw.get("level", 1)),
                "source": raw.get("source", "user"),
                "locked": bool(raw.get("locked", False)),
                "section_key": raw.get("section_key") or raw.get("key") or section_key(title),
                "content_mode": mode,
                "content_json": content,
                "children": normalize_template_nodes(raw.get("children", [])),
            }
        )
    return result


def _convert(node: dict[str, Any], source: str) -> dict[str, Any]:
    converted = copy.deepcopy(node)
    converted["source"] = source
    converted["locked"] = bool(node.get("locked", False))
    converted["children"] = [_convert(child, source) for child in converted.get("children", [])]
    return converted


def _matching(root: list[dict[str, Any]], title: str) -> list[dict[str, Any]]:
    return [node for node in walk_nodes(root) if titles_match(node["title"], title)]


def _merge_content(
    target: dict[str, Any], user: dict[str, Any], ambiguities: list[dict[str, Any]]
) -> None:
    if target.get("content_mode") == "placeholder" and user.get("content_json"):
        target["content_json"] = copy.deepcopy(user["content_json"])
        target["content_mode"] = "fixed_text"
    elif target.get("source") == "tender" and user.get("content_json"):
        supplement = _convert(user, "user_supplement")
        supplement["children"] = []
        target["children"].append(supplement)
    for child in user.get("children", []):
        matches = [
            candidate
            for candidate in target["children"]
            if titles_match(candidate["title"], child["title"])
        ]
        if len(matches) > 1:
            unresolved = _convert(child, "user_supplement")
            unresolved["mapping_status"] = "needs_review"
            unresolved["mapping_candidates"] = [node["title"] for node in matches]
            target["children"].append(unresolved)
            ambiguities.append(
                {"title": child["title"], "candidates": unresolved["mapping_candidates"]}
            )
        elif len(matches) == 1 and canonical(matches[0]["title"]) == canonical(child["title"]):
            _merge_content(matches[0], child, ambiguities)
        elif len(matches) == 1:
            matches[0]["children"].append(_convert(child, "user_supplement"))
        else:
            target["children"].append(_convert(child, "user_supplement"))


def merge_trees(
    tender: list[dict[str, Any]],
    template: list[dict[str, Any]],
    omit_titles: list[str] | None = None,
) -> dict[str, Any]:
    root = copy.deepcopy(tender)
    omitted = set(omit_titles or [])
    ambiguities = []
    remaining = []
    for raw_user in normalize_template_nodes(template):
        if any(titles_match(raw_user["title"], title) for title in omitted):
            continue
        user = _convert(raw_user, "user_only")
        matches = _matching(root, user["title"])
        if len(matches) > 1:
            user["mapping_status"] = "needs_review"
            user["mapping_candidates"] = [node["title"] for node in matches]
            remaining.append(user)
            ambiguities.append({"title": user["title"], "candidates": user["mapping_candidates"]})
            continue
        if len(matches) == 1:
            target = matches[0]
            if canonical(target["title"]) == canonical(user["title"]):
                _merge_content(target, user, ambiguities)
            else:
                user["source"] = "user_supplement"
                target["children"].append(user)
            continue
        affinity_parent = None
        for user_keys, parent_keys in AFFINITY:
            if canonical(user["title"]) in user_keys:
                affinity_parent = next(
                    (node for node in walk_nodes(root) if canonical(node["title"]) in parent_keys),
                    None,
                )
                if affinity_parent:
                    break
        if affinity_parent:
            user["source"] = "user_supplement"
            affinity_parent["children"].append(user)
        else:
            remaining.append(user)
    root.extend(remaining)
    return {"nodes": root, "ambiguities": ambiguities, "stats": tree_stats(root)}


def tree_stats(nodes: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"tender": 0, "user_supplement": 0, "user_only": 0, "placeholders": 0}
    for node in walk_nodes(nodes):
        stats[node["source"]] = stats.get(node["source"], 0) + 1
        stats["placeholders"] += int(
            node.get("content_mode") == "placeholder" and not node.get("children")
        )
    return stats
