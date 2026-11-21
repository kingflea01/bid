from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import bad_request
from app.models.section import ProjectSection


def display_numbers(sections: list[ProjectSection]) -> dict[str, str]:
    children: dict[str | None, list[ProjectSection]] = {}
    for section in sections:
        children.setdefault(section.parent_id, []).append(section)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.position, item.created_at, item.id))
    result = {}

    def visit(parent_id: str | None, prefix: str = "") -> None:
        for index, section in enumerate(children.get(parent_id, []), 1):
            number = f"{prefix}.{index}" if prefix else str(index)
            result[section.id] = number
            visit(section.id, number)

    visit(None)
    return result


def move_section(
    db: Session, section: ProjectSection, parent_id: str | None, position: int
) -> None:
    if section.locked:
        raise bad_request("招标固定章节不可移动", code="section_locked")
    if parent_id == section.id:
        raise bad_request("章节不能移动到自身之下", code="section_cycle")
    parent = db.get(ProjectSection, parent_id) if parent_id else None
    if parent_id and (parent is None or parent.project_id != section.project_id):
        raise bad_request("目标父章节无效", code="invalid_parent")
    if parent and parent.locked and section.parent_id != parent.id:
        raise bad_request("不能改变招标固定章节的子结构", code="section_locked")
    cursor = parent
    while cursor:
        if cursor.id == section.id:
            raise bad_request("不能移动到后代章节之下", code="section_cycle")
        cursor = db.get(ProjectSection, cursor.parent_id) if cursor.parent_id else None
    siblings = db.scalars(
        select(ProjectSection)
        .where(
            ProjectSection.project_id == section.project_id,
            ProjectSection.parent_id == parent_id,
            ProjectSection.id != section.id,
        )
        .order_by(ProjectSection.position)
    ).all()
    if position < 0 or position > len(siblings):
        raise bad_request("目标位置超出范围", code="invalid_position")
    old_siblings = db.scalars(
        select(ProjectSection)
        .where(
            ProjectSection.project_id == section.project_id,
            ProjectSection.parent_id == section.parent_id,
            ProjectSection.id != section.id,
        )
        .order_by(ProjectSection.position)
    ).all()
    for index, sibling in enumerate(old_siblings):
        sibling.position = index
    siblings.insert(position, section)
    section.parent_id = parent_id
    for index, sibling in enumerate(siblings):
        sibling.position = index
    section.version += 1
