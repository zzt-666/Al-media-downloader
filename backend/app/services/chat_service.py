"""AI Q&A over an already-produced summary / transcript (extension module)."""

from __future__ import annotations

import logging
from typing import Any, Iterator

from app.config import SUMMARY_MAX_TRANSCRIPT_CHARS
from app.schemas import ChatMessage, ChatStreamRequest
from app.services import llm_client
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)

_SYSTEM = """你是视频学习助手。用户会基于当前视频内容提问。
规则：
1. 优先依据提供的摘要、章节、知识点与字幕回答；
2. 字幕未覆盖的内容请明确说不确定，不要编造；
3. 回答使用简体中文，条理清晰，可适当引用时间戳；
4. 不要输出与问题无关的开场套话。"""


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    tail = limit - head - 60
    return text[:head] + "\n\n…[中间已省略]…\n\n" + text[-max(tail, 0) :]


def _build_context(body: ChatStreamRequest) -> str:
    chapters = body.chapters or []
    key_points = body.key_points or []
    chapter_block = "\n".join(
        f"- [{c.start}] {c.title}: {c.summary}" for c in chapters
    ) or "（无）"
    points_block = "\n".join(
        f"- [{k.timestamp}] {k.text}" for k in key_points
    ) or "（无）"
    transcript = (body.transcript or "").strip()
    if transcript:
        # Reserve room for summary + chat turns
        transcript = _truncate(transcript, min(SUMMARY_MAX_TRANSCRIPT_CHARS, 24000))
    else:
        transcript = "（无字幕原文）"

    return (
        f"视频标题：{body.title}\n\n"
        f"整体摘要：\n{body.summary or '（无）'}\n\n"
        f"章节大纲：\n{chapter_block}\n\n"
        f"核心知识点：\n{points_block}\n\n"
        f"字幕原文：\n{transcript}"
    )


def _normalize_messages(messages: list[ChatMessage]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = m.role if m.role in ("user", "assistant") else "user"
        content = (m.content or "").strip()
        if not content:
            continue
        out.append({"role": role, "content": content})
    if not out or out[-1]["role"] != "user":
        raise ServiceError("请先输入要提问的内容", status_code=400)
    # Cap history to last 12 turns
    return out[-12:]


def iter_chat_events(body: ChatStreamRequest) -> Iterator[dict[str, Any]]:
    try:
        llm_client.require_llm_key()
        if not body.summary.strip() and not (body.transcript or "").strip():
            raise ServiceError("请先完成视频总结后再进行 AI 对话", status_code=400)

        history = _normalize_messages(body.messages)
        context = _build_context(body)
        messages = [
            {"role": "system", "content": _SYSTEM},
            {
                "role": "user",
                "content": f"以下是当前视频的学习材料，供后续问答参考：\n\n{context}",
            },
            {
                "role": "assistant",
                "content": "好的，我已了解该视频内容。请提问。",
            },
            *history,
        ]

        yield {"event": "status", "data": {"stage": "answering"}}
        parts: list[str] = []
        for piece in llm_client.iter_chat_deltas(messages):
            parts.append(piece)
            yield {"event": "delta", "data": {"text": piece}}
        answer = "".join(parts).strip()
        if not answer:
            raise ServiceError("AI 未返回有效回答，请稍后重试", status_code=502)
        yield {"event": "done", "data": {"content": answer}}
    except ServiceError as exc:
        yield {
            "event": "error",
            "data": {"detail": exc.detail, "status_code": exc.status_code},
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Chat stream failed: %s", exc)
        yield {
            "event": "error",
            "data": {"detail": "AI 对话失败，请稍后重试", "status_code": 502},
        }
