"""Merge the tender response-format outline with a user Markdown template."""

import json
import re
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[2]

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
HINT_RE = re.compile(r"^>\s*提示[:：]\s*(.*)$")
CONTENT_RE = re.compile(r"^>\s*内容模板[:：]\s*(.*)$")
PLACEHOLDER_RE = re.compile(r"\[\[(.+?)\]\]")

SYNONYM_GROUPS = [
    {"响应函", "投标函", "报价函"},
    {"授权委托书", "法定代表人授权书", "授权书"},
    {"商务资料", "资格审查资料", "资格证明文件"},
    {"响应方案", "技术方案", "服务方案"},
    {"报价表", "报价一览表", "分项报价表", "分项报价一览表"},
    {"偏差表", "偏离表", "技术条款偏差表", "商务条款偏差表"},
    {"响应保证金", "投标保证金"},
    {"公司简介", "基本情况", "情况简介", "简介"},
    {"资质证书", "营业执照资质证书等", "营业执照"},
    {"业绩证明", "类似项目情况表", "近三年类似项目情况表"},
    {"理解", "项目理解", "对项目的理解"},
    {"售后服务承诺", "售后服务", "服务承诺"},
    {"附件清单", "其他材料", "其它材料"},
]


def canonical(text):
    value = re.sub(r"^\d+(\.\d+)*[\.、]?\s*", "", text)
    value = re.sub(r"^[一二三四五六七八九十]+、\s*", "", value)
    value = re.sub(r"[（(][^）)]*[）)]", "", value)
    value = re.sub(r"[；。：，、\s]", "", value)
    value = re.sub(r"^(对|关于)", "", value)
    for prefix in ("供应商", "近三年", "项目", "公司"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.replace("认为应该附", "")
    value = value.replace("的", "")
    value = value.replace("其它", "其他")
    return value


def group_id(text):
    key = canonical(text)
    for index, group in enumerate(SYNONYM_GROUPS):
        if key in group:
            return index
    return None


def titles_match(left, right):
    if canonical(left) == canonical(right):
        return True
    left_group = group_id(left)
    return left_group is not None and left_group == group_id(right)


def new_tender_node(item):
    return {
        "title": item["text"],
        "level": item["level"],
        "source": "tender",
        "source_index": item.get("source_index", item.get("index")),
        "source_end": item.get("source_end"),
        "content_mode": "tender_template",
        "content_template": None,
        "hints": [],
        "content_lines": [],
        "placeholders": [],
        "children": [],
    }


def parse_markdown_template(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    root = []
    stack = []
    current = None
    preamble = []

    for raw in lines:
        line = raw.rstrip()
        heading = HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            node = {
                "title": title,
                "level": level,
                "source": "user",
                "content_mode": "placeholder",
                "content_template": None,
                "hints": [],
                "content_lines": [],
                "placeholders": [],
                "children": [],
            }
            while stack and stack[-1]["level"] >= level:
                stack.pop()
            if stack:
                stack[-1]["children"].append(node)
            else:
                root.append(node)
            stack.append(node)
            current = node
            continue

        if not line.strip():
            continue
        if current is None:
            preamble.append(line.strip())
            continue

        hint = HINT_RE.match(line.strip())
        if hint:
            current["hints"].append(hint.group(1).strip())
            continue
        content = CONTENT_RE.match(line.strip())
        if content:
            current["content_template"] = content.group(1).strip()
            continue
        if line.strip().startswith(">"):
            current["hints"].append(line.strip().lstrip(">").strip())
            continue

        current["content_lines"].append(line.strip())
        current["placeholders"].extend(PLACEHOLDER_RE.findall(line))

    def finalize(node):
        if node["content_template"]:
            node["content_mode"] = "content_template"
        elif node["content_lines"]:
            node["content_mode"] = "fixed_text"
        else:
            node["content_mode"] = "placeholder"
        for child in node["children"]:
            finalize(child)

    for node in root:
        finalize(node)

    if len(root) == 1 and root[0]["children"]:
        root = root[0]["children"]

    return root, preamble


def build_tender_tree(outline):
    root = []
    stack = []
    for item in outline:
        node = new_tender_node(item)
        while stack and stack[-1]["level"] >= node["level"]:
            stack.pop()
        if stack:
            stack[-1]["children"].append(node)
        else:
            root.append(node)
        stack.append(node)
    return root


def to_supplement(node):
    node = dict(node)
    node["source"] = "user_supplement"
    node["children"] = [to_supplement(child) for child in node["children"]]
    return node


def to_user_only(node):
    node = dict(node)
    node["source"] = "user_only"
    node["children"] = [to_user_only(child) for child in node["children"]]
    return node


def merge_level(tender_nodes, user_nodes):
    consumed = set()
    for tender in tender_nodes:
        matches = [
            user
            for user in user_nodes
            if id(user) not in consumed and titles_match(tender["title"], user["title"])
        ]
        for user in matches:
            consumed.add(id(user))
            if canonical(tender["title"]) == canonical(user["title"]):
                tender["hints"].extend(user["hints"])
                if user["content_mode"] != "placeholder":
                    tender["children"].append(to_supplement(user))
                merge_level(tender["children"], user["children"])
            else:
                tender["children"].append(to_supplement(user))
    for user in user_nodes:
        if id(user) not in consumed:
            tender_nodes.append(to_user_only(user))


def walk_nodes(nodes):
    for node in nodes:
        yield node
        yield from walk_nodes(node["children"])


def find_global_match(root, user):
    for node in walk_nodes(root):
        if titles_match(node["title"], user["title"]):
            return node
    return None


def place_global(root, user):
    target = find_global_match(root, user)
    if target is None:
        return False
    if canonical(target["title"]) == canonical(user["title"]):
        target["hints"].extend(user["hints"])
        if user["content_mode"] != "placeholder":
            target["children"].append(to_supplement(user))
    else:
        target["children"].append(to_supplement(user))
    return True


AFFINITY = [
    ({"售后服务承诺", "售后服务", "服务承诺"}, {"响应方案", "技术方案", "服务方案"}),
    ({"附件清单"}, {"商务资料", "其他材料", "其它材料"}),
    ({"公司简介", "资质证书", "业绩证明"}, {"商务资料", "资格证明文件", "供应商基本情况"}),
]


def find_affinity_parent(root, user):
    key = canonical(user["title"])
    for user_keys, parent_keys in AFFINITY:
        if key not in user_keys:
            continue
        for node in walk_nodes(root):
            if canonical(node["title"]) in parent_keys:
                return node
    return None


def merge_trees(tender_tree, user_nodes):
    remaining = []
    for user in user_nodes:
        if any(titles_match(node["title"], user["title"]) for node in tender_tree):
            remaining.append(user)
            continue
        if place_global(tender_tree, user):
            continue
        parent = find_affinity_parent(tender_tree, user)
        if parent is not None:
            parent["children"].append(to_supplement(user))
            continue
        remaining.append(user)
    merge_level(tender_tree, remaining)


def count_nodes(nodes):
    stats = {
        "tender": 0,
        "user_supplement": 0,
        "user_only": 0,
        "content_template": 0,
        "fixed_text": 0,
        "placeholder": 0,
        "placeholders": 0,
    }
    for node in nodes:
        stats["tender"] += node["source"] == "tender"
        stats["user_supplement"] += node["source"] == "user_supplement"
        stats["user_only"] += node["source"] == "user_only"
        stats[node["content_mode"]] = stats.get(node["content_mode"], 0) + 1
        stats["placeholders"] += len(node["placeholders"])
        child_stats = count_nodes(node["children"])
        for key, value in child_stats.items():
            stats[key] += value
    return stats


def render_node(node, depth, lines):
    indent = "   " * depth
    if node["source"] == "tender":
        label = "招标 | " + (
            "模板" if node["content_mode"] == "tender_template" else "待编写"
        )
    else:
        prefix = "用户补充" if node["source"] == "user_supplement" else "用户独有"
        mode = {
            "content_template": "内容模板：" + (node["content_template"] or ""),
            "fixed_text": "固定正文",
            "placeholder": "待编写",
        }[node["content_mode"]]
        label = prefix + " | " + mode
    lines.append(f"{indent}- {node['title']}  [{label}]")
    for hint in node["hints"]:
        lines.append(f"{indent}  > 提示：{hint}")
    for child in node["children"]:
        render_node(child, depth + 1, lines)


def render_structure_md(merged, tender_meta, template_path, stats, warnings):
    lines = ["# 标书结构", ""]
    lines.append(f"- 项目：{tender_meta.get('project_name', '未命名项目')}")
    lines.append(f"- 项目编号：{tender_meta.get('project_number', '未载明')}")
    lines.append(f"- 包号：{tender_meta.get('package', '未指定')}")
    lines.append(f"- 招标章节来源：{tender_meta.get('format_chapter', '未识别')}")
    lines.append(f"- 用户模板：{template_path}")
    lines.append("")
    lines.append("## 合并结果")
    lines.append("")
    for node in merged:
        render_node(node, 0, lines)
    lines.append("")
    lines.append("## 统计")
    lines.append("")
    lines.append("| 指标 | 数量 |")
    lines.append("|---|---:|")
    lines.append(f"| 招标章节 | {stats['tender']} |")
    lines.append(f"| 用户补充 | {stats['user_supplement']} |")
    lines.append(f"| 用户独有 | {stats['user_only']} |")
    lines.append(f"| 内容模板 | {stats['content_template']} |")
    lines.append(f"| 固定正文 | {stats['fixed_text']} |")
    lines.append(f"| 待编写 | {stats['placeholder']} |")
    lines.append(f"| 占位符 | {stats['placeholders']} |")
    lines.append("")
    if warnings:
        lines.append("## 待确认")
        lines.append("")
        for warning in warnings:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def build_structure(tender_json_path, template_path, package, output_dir):
    tender = json.loads(Path(tender_json_path).read_text(encoding="utf-8"))
    user_nodes, preamble = parse_markdown_template(template_path)
    format_chapter = tender.get("format_chapter") or {}
    outline = tender["outline"]
    for index, item in enumerate(outline):
        item["source_index"] = item["index"]
        item["source_end"] = (
            outline[index + 1]["index"]
            if index + 1 < len(outline)
            else format_chapter.get("end")
        )
    tender_tree = build_tender_tree(outline)
    merge_trees(tender_tree, user_nodes)

    stats = count_nodes(tender_tree)
    metadata = dict(tender.get("metadata", {}))
    metadata["package"] = package
    metadata["format_chapter"] = format_chapter.get("text", "未识别")

    warnings = []
    if not format_chapter:
        warnings.append("未识别到招标文件的响应文件格式章节，已仅使用用户模板。")
    if not user_nodes:
        warnings.append("用户模板为空。")
    if preamble:
        warnings.append("用户模板首个标题之前存在说明文字，已忽略。")
    unresolved = []
    for node in user_nodes:
        if node["content_mode"] == "content_template" and node["content_template"]:
            raw = node["content_template"]
            candidates = [
                Path(template_path).parent / raw,
                SKILL_DIR / "config" / raw,
                Path.cwd() / raw,
            ]
            resolved = next((path for path in candidates if path.exists()), None)
            if resolved is None:
                unresolved.append(f"{node['title']}：内容模板不存在 {raw}")
    warnings.extend(unresolved)

    structure = {
        "metadata": metadata,
        "template": str(template_path),
        "format_chapter": format_chapter,
        "nodes": tender_tree,
        "stats": stats,
        "warnings": warnings,
    }

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "structure.json").write_text(
        json.dumps(structure, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = render_structure_md(
        tender_tree, metadata, template_path, stats, warnings
    )
    (output_dir / "structure.md").write_text(markdown, encoding="utf-8")
    return structure


def timed_build_structure(tender_json_path, template_path, package, output_dir):
    start = time.perf_counter()
    result = build_structure(tender_json_path, template_path, package, output_dir)
    result["timing"] = {"structure_ms": round((time.perf_counter() - start) * 1000, 2)}
    return result
