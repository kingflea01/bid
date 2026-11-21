from datetime import date, datetime
from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import conflict


def commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise conflict("数据与现有记录冲突，请检查唯一编号或关联关系") from exc


def model_dict(model: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    excluded = exclude or set()
    result = {}
    for column in inspect(type(model)).columns:
        key = column.key
        if key not in excluded:
            value = getattr(model, key)
            if isinstance(value, (datetime, date)):
                value = value.isoformat()
            result[key] = value
    return result


def models_dict(models: list[Any], exclude: set[str] | None = None) -> list[dict[str, Any]]:
    return [model_dict(model, exclude) for model in models]
