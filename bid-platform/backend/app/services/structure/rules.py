import re
from typing import Any

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
AFFINITY = [
    ({"售后服务承诺", "售后服务", "服务承诺"}, {"响应方案", "技术方案", "服务方案"}),
    ({"附件清单"}, {"商务资料", "其他材料", "其它材料"}),
    ({"公司简介", "资质证书", "业绩证明"}, {"商务资料", "资格证明文件", "供应商基本情况"}),
]


def canonical(text: str) -> str:
    value = re.sub(r"^\d+(\.\d+)*[\.、]?\s*", "", text)
    value = re.sub(r"^[一二三四五六七八九十]+、\s*", "", value)
    value = re.sub(r"[（(][^）)]*[）)]", "", value)
    value = re.sub(r"[；。：，、\s]", "", value)
    value = re.sub(r"^(对|关于)", "", value)
    for prefix in ("供应商", "近三年", "项目", "公司"):
        if value.startswith(prefix):
            value = value[len(prefix) :]
    return value.replace("认为应该附", "").replace("的", "").replace("其它", "其他")


def group_id(text: str) -> int | None:
    key = canonical(text)
    return next((index for index, group in enumerate(SYNONYM_GROUPS) if key in group), None)


def titles_match(left: str, right: str) -> bool:
    if canonical(left) == canonical(right):
        return True
    left_group = group_id(left)
    return left_group is not None and left_group == group_id(right)


def normalize_terminology(text: str, response_term: str, award_term: str) -> str:
    if response_term == "响应":
        text = text.replace("投标", "响应")
    else:
        text = text.replace("响应", "投标")
    return (
        text.replace("成交", award_term)
        if award_term == "中标"
        else text.replace("中标", award_term)
    )


def section_key(title: str) -> str:
    return canonical(title)[:240]


def walk_nodes(nodes: list[dict[str, Any]]):
    for node in nodes:
        yield node
        yield from walk_nodes(node.get("children", []))
