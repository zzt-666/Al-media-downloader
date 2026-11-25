"""Shared OpenAI-compatible LLM helpers for summary extensions.

Intentionally separate from summary_service so existing summarize flow stays closed.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Iterator

import httpx

from app.config import (
    SUMMARY_LLM_API_KEY,
    SUMMARY_LLM_BASE_URL,
    SUMMARY_LLM_MODEL,
    SUMMARY_TIMEOUT_SECONDS,
)
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)


def llm_configured() -> bool:
    return bool(SUMMARY_LLM_API_KEY)


def require_llm_key() -> None:
    if not SUMMARY_LLM_API_KEY:
        raise ServiceError(
            "未配置 SUMMARY_LLM_API_KEY。请在环境变量中设置 OpenAI 兼容 API Key 后重试。",
            status_code=422,
        )


def chat_url() -> str:
    return f"{SUMMARY_LLM_BASE_URL}/chat/completions"


def headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {SUMMARY_LLM_API_KEY}",
        "Content-Type": "application/json",
    }


def post_chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.3,
    json_mode: bool = False,
) -> str:
    require_llm_key()
    payload: dict[str, Any] = {
        "model": SUMMARY_LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    try:
        with httpx.Client(timeout=SUMMARY_TIMEOUT_SECONDS) as client:
            resp = client.post(chat_url(), headers=headers(), json=payload)
            if resp.status_code >= 400 and json_mode:
                plain = {k: v for k, v in payload.items() if k != "response_format"}
                resp = client.post(chat_url(), headers=headers(), json=plain)
            if resp.status_code >= 400:
                detail = resp.text[:300]
                logger.warning("LLM HTTP %s: %s", resp.status_code, detail)
                raise ServiceError(
                    f"AI 服务调用失败（HTTP {resp.status_code}），请检查 Key / 额度后重试",
                    status_code=502,
                )
            body = resp.json()
    except ServiceError:
        raise
    except httpx.TimeoutException as exc:
        raise ServiceError("AI 服务超时，请稍后重试", status_code=504) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM call failed")
        raise ServiceError("AI 服务不可用，请稍后重试", status_code=502) from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ServiceError("AI 返回内容为空，请稍后重试", status_code=502) from exc
    if not isinstance(content, str) or not content.strip():
        raise ServiceError("AI 返回内容为空，请稍后重试", status_code=502)
    return content


def iter_chat_deltas(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.4,
) -> Iterator[str]:
    require_llm_key()
    payload = {
        "model": SUMMARY_LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "stream": True,
    }
    try:
        with httpx.Client(timeout=SUMMARY_TIMEOUT_SECONDS) as client:
            with client.stream(
                "POST", chat_url(), headers=headers(), json=payload
            ) as resp:
                if resp.status_code >= 400:
                    detail = resp.read().decode("utf-8", errors="replace")[:300]
                    logger.warning("LLM stream HTTP %s: %s", resp.status_code, detail)
                    raise ServiceError(
                        f"AI 服务调用失败（HTTP {resp.status_code}），请检查 Key / 额度后重试",
                        status_code=502,
                    )
                for line in resp.iter_lines():
                    if not line or line.startswith(":") or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    try:
                        delta = chunk["choices"][0].get("delta") or {}
                        piece = delta.get("content")
                    except (KeyError, IndexError, TypeError):
                        continue
                    if isinstance(piece, str) and piece:
                        yield piece
    except ServiceError:
        raise
    except httpx.TimeoutException as exc:
        raise ServiceError("AI 服务超时，请稍后重试", status_code=504) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM stream failed")
        raise ServiceError("AI 服务不可用，请稍后重试", status_code=502) from exc
