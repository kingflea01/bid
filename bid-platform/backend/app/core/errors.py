from typing import Any


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def not_found(entity: str = "资源") -> AppError:
    return AppError(404, "not_found", f"{entity}不存在或无权访问")


def conflict(message: str, details: Any = None) -> AppError:
    return AppError(409, "conflict", message, details)


def forbidden(message: str = "无权执行此操作") -> AppError:
    return AppError(403, "forbidden", message)


def bad_request(message: str, details: Any = None, code: str = "bad_request") -> AppError:
    return AppError(400, code, message, details)
