import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.errors import AppError


class AIGateway:
    def complete(
        self, *, system_prompt: str, input_payload: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any], int]:
        settings = get_settings()
        if not settings.ai_enabled or not settings.ai_base_url or not settings.ai_model:
            raise AppError(503, "ai_disabled", "AI 未启用或配置不完整")
        if not settings.ai_base_url.startswith(("https://", "http://")):
            raise AppError(503, "ai_configuration_error", "AI 接口地址无效")
        url = f"{settings.ai_base_url.rstrip('/')}/chat/completions"
        headers = {"Content-Type": "application/json"}
        if settings.ai_api_key:
            headers["Authorization"] = f"Bearer {settings.ai_api_key}"
        body = {
            "model": settings.ai_model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(input_payload, ensure_ascii=False, separators=(",", ":")),
                },
            ],
        }
        attempts = 0
        with httpx.Client(timeout=settings.ai_timeout_seconds, trust_env=True) as client:
            while True:
                attempts += 1
                try:
                    response = client.post(url, headers=headers, json=body)
                    if response.status_code >= 500 and attempts == 1:
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    content = payload["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("non-text model content")
                    return json.loads(content), payload.get("usage") or {}, attempts
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    if attempts == 1:
                        continue
                    raise AppError(502, "ai_network_error", "AI 接口网络请求失败") from exc
                except httpx.HTTPStatusError as exc:
                    code = (
                        "ai_upstream_error"
                        if exc.response.status_code >= 500
                        else "ai_request_rejected"
                    )
                    raise AppError(502, code, "AI 接口请求失败") from exc
                except (ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
                    raise AppError(422, "invalid_ai_output", "AI 输出不是有效 JSON 契约") from exc
