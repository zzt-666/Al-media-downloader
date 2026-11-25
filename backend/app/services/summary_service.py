from __future__ import annotations

import json
import logging
import re
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any, Iterator

import httpx

from app.config import (
    SUMMARY_LLM_API_KEY,
    SUMMARY_LLM_BASE_URL,
    SUMMARY_LLM_MODEL,
    SUMMARY_MAX_TRANSCRIPT_CHARS,
    SUMMARY_TIMEOUT_SECONDS,
)
from app.schemas import SummarizeResponse, SummaryChapter, SummaryKeyPoint
from app.services.subtitle_service import TranscriptResult, fetch_transcript
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """你是视频学习助手。根据带时间戳的字幕文稿，输出 JSON（不要 Markdown 围栏），字段：
{
  "summary": "200-400字整体摘要，中文",
  "chapters": [{"start":"MM:SS或HH:MM:SS","title":"章节标题","summary":"章节要点"}],
  "key_points": [{"timestamp":"MM:SS或HH:MM:SS","text":"知识点"}]
}
要求：
1. chapters 按时间顺序，覆盖全片主要结构，约 3-12 章；
2. key_points 提炼 5-12 条核心知识，timestamp 尽量对齐字幕；
3. 只依据字幕，不编造字幕未出现的事实；
4. 全文使用简体中文。"""

_SUMMARY_STREAM_SYSTEM = """你是视频学习助手。根据带时间戳的字幕文稿，用简体中文写一段 200-400 字的整体摘要。
要求：
1. 只输出摘要正文，不要标题、不要 Markdown、不要 JSON、不要列表符号；
2. 只依据字幕，不编造字幕未出现的事实；
3. 覆盖视频主旨与关键结论，语言流畅可读。"""

_STRUCTURE_SYSTEM = """你是视频学习助手。根据带时间戳的字幕文稿，输出 JSON（不要 Markdown 围栏），字段：
{
  "chapters": [{"start":"MM:SS或HH:MM:SS","title":"章节标题","summary":"本章要点，2-4句"}],
  "key_points": [{"timestamp":"MM:SS或HH:MM:SS","text":"知识点"}]
}
要求：
1. chapters 按时间顺序，覆盖全片主要结构，约 3-12 章；
2. key_points 提炼 5-12 条核心知识，timestamp 尽量对齐字幕；
3. 只依据字幕，不编造字幕未出现的事实；
4. 全文使用简体中文。"""


def llm_configured() -> bool:
    return bool(SUMMARY_LLM_API_KEY)


def _truncate_transcript(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    head = int(limit * 0.7)
    tail = limit - head - 80
    return (
        text[:head]
        + "\n\n…[中间字幕已省略以适配上下文]…\n\n"
        + text[-max(tail, 0) :]
    )


def _extract_json_object(content: str) -> dict[str, Any]:
    content = content.strip()
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*", "", content)
        content = re.sub(r"\s*```$", "", content)
    try:
        data = json.loads(content)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", content)
    if not match:
        raise ServiceError("AI 返回格式异常，请稍后重试", status_code=502)
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise ServiceError("AI 返回格式异常，请稍后重试", status_code=502) from exc
    if not isinstance(data, dict):
        raise ServiceError("AI 返回格式异常，请稍后重试", status_code=502)
    return data


def _require_llm_key() -> None:
    if not SUMMARY_LLM_API_KEY:
        raise ServiceError(
            "未配置 SUMMARY_LLM_API_KEY。请在环境变量中设置 OpenAI 兼容 API Key 后重试。",
            status_code=422,
        )


def _llm_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {SUMMARY_LLM_API_KEY}",
        "Content-Type": "application/json",
    }


def _chat_url() -> str:
    return f"{SUMMARY_LLM_BASE_URL}/chat/completions"


def _post_chat(payload: dict[str, Any]) -> str:
    """Non-streaming chat completion; returns assistant message content."""
    headers = _llm_headers()
    try:
        with httpx.Client(timeout=SUMMARY_TIMEOUT_SECONDS) as client:
            resp = client.post(_chat_url(), headers=headers, json=payload)
            if resp.status_code >= 400 and payload.get("response_format"):
                plain = {k: v for k, v in payload.items() if k != "response_format"}
                resp = client.post(_chat_url(), headers=headers, json=plain)
            if resp.status_code >= 400:
                detail = resp.text[:300]
                logger.warning("LLM HTTP %s: %s", resp.status_code, detail)
                raise ServiceError(
                    f"AI 总结服务调用失败（HTTP {resp.status_code}），请检查 Key / 额度后重试",
                    status_code=502,
                )
            body = resp.json()
    except ServiceError:
        raise
    except httpx.TimeoutException as exc:
        raise ServiceError("AI 总结超时，请稍后重试或缩短视频", status_code=504) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM call failed")
        raise ServiceError("AI 总结服务不可用，请稍后重试", status_code=502) from exc

    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ServiceError("AI 返回内容为空，请稍后重试", status_code=502) from exc
    if not isinstance(content, str) or not content.strip():
        raise ServiceError("AI 返回内容为空，请稍后重试", status_code=502)
    return content


def _call_llm(title: str, transcript: str) -> dict[str, Any]:
    _require_llm_key()
    user_prompt = (
        f"视频标题：{title}\n\n字幕文稿（带时间戳）：\n{transcript}\n\n"
        "请按系统要求输出 JSON。"
    )
    payload = {
        "model": SUMMARY_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    return _extract_json_object(_post_chat(payload))


def _call_structure_llm(title: str, transcript: str) -> dict[str, Any]:
    _require_llm_key()
    user_prompt = (
        f"视频标题：{title}\n\n字幕文稿（带时间戳）：\n{transcript}\n\n"
        "请按系统要求输出章节大纲与核心知识点 JSON。"
    )
    payload = {
        "model": SUMMARY_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _STRUCTURE_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
    }
    return _extract_json_object(_post_chat(payload))


def _iter_stream_summary(title: str, transcript: str) -> Iterator[str]:
    """Yield text deltas for the overall summary (OpenAI-compatible stream)."""
    _require_llm_key()
    user_prompt = (
        f"视频标题：{title}\n\n字幕文稿（带时间戳）：\n{transcript}\n\n"
        "请直接输出整体摘要正文。"
    )
    payload = {
        "model": SUMMARY_LLM_MODEL,
        "messages": [
            {"role": "system", "content": _SUMMARY_STREAM_SYSTEM},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.3,
        "stream": True,
    }
    headers = _llm_headers()
    try:
        with httpx.Client(timeout=SUMMARY_TIMEOUT_SECONDS) as client:
            with client.stream(
                "POST", _chat_url(), headers=headers, json=payload
            ) as resp:
                if resp.status_code >= 400:
                    # Drain body for error detail then fail.
                    detail = resp.read().decode("utf-8", errors="replace")[:300]
                    logger.warning("LLM stream HTTP %s: %s", resp.status_code, detail)
                    raise ServiceError(
                        f"AI 总结服务调用失败（HTTP {resp.status_code}），请检查 Key / 额度后重试",
                        status_code=502,
                    )
                for line in resp.iter_lines():
                    if not line:
                        continue
                    if line.startswith(":"):
                        continue
                    if not line.startswith("data:"):
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
        raise ServiceError("AI 总结超时，请稍后重试或缩短视频", status_code=504) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("LLM stream failed")
        raise ServiceError("AI 总结服务不可用，请稍后重试", status_code=502) from exc


def _to_chapters(raw: Any) -> list[SummaryChapter]:
    if not isinstance(raw, list):
        return []
    out: list[SummaryChapter] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        start = str(item.get("start") or item.get("timestamp") or "00:00").strip()
        summary = str(item.get("summary") or item.get("text") or "").strip()
        if not title and not summary:
            continue
        out.append(
            SummaryChapter(
                start=start or "00:00",
                title=title or "章节",
                summary=summary,
            )
        )
    return out


def _to_key_points(raw: Any) -> list[SummaryKeyPoint]:
    if not isinstance(raw, list):
        return []
    out: list[SummaryKeyPoint] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text") or item.get("point") or "").strip()
        ts = str(item.get("timestamp") or item.get("start") or "").strip() or "—"
        if not text:
            continue
        out.append(SummaryKeyPoint(timestamp=ts, text=text))
    return out


def build_markdown(
    title: str,
    summary: str,
    chapters: list[SummaryChapter],
    key_points: list[SummaryKeyPoint],
) -> str:
    lines = [f"# {title}", "", "## 整体摘要", "", summary.strip() or "（无）", ""]
    lines.extend(["## 章节大纲", ""])
    if chapters:
        for ch in chapters:
            lines.append(f"### [{ch.start}] {ch.title}")
            if ch.summary:
                lines.append("")
                lines.append(ch.summary)
            lines.append("")
    else:
        lines.append("（无）")
        lines.append("")
    lines.extend(["## 核心知识点", ""])
    if key_points:
        for kp in key_points:
            lines.append(f"- **[{kp.timestamp}]** {kp.text}")
    else:
        lines.append("- （无）")
    lines.append("")
    return "\n".join(lines).strip() + "\n"


def summarize_from_transcript(tr: TranscriptResult) -> SummarizeResponse:
    clipped = _truncate_transcript(tr.text, SUMMARY_MAX_TRANSCRIPT_CHARS)
    data = _call_llm(tr.title, clipped)
    summary = str(data.get("summary") or "").strip()
    chapters = _to_chapters(data.get("chapters"))
    key_points = _to_key_points(data.get("key_points"))
    if not summary and not chapters and not key_points:
        raise ServiceError("AI 未能生成有效总结，请稍后重试", status_code=502)
    if not summary:
        summary = "（模型未返回整体摘要，请参考章节与要点。）"
    md = build_markdown(tr.title, summary, chapters, key_points)
    return SummarizeResponse(
        title=tr.title,
        source_lang=tr.language,
        subtitle_kind=tr.kind,  # type: ignore[arg-type]
        summary=summary,
        chapters=chapters,
        key_points=key_points,
        markdown=md,
        transcript=tr.text,
    )


def summarize(url: str) -> SummarizeResponse:
    if not llm_configured():
        raise ServiceError(
            "未配置 SUMMARY_LLM_API_KEY。请在环境变量中设置 OpenAI 兼容 API Key 后重试。",
            status_code=422,
        )
    tr = fetch_transcript(url)
    return summarize_from_transcript(tr)


def iter_summarize_events(url: str) -> Iterator[dict[str, Any]]:
    """
    Yield SSE event payloads for streaming summary.

    Events:
      - status: {stage}
      - meta: {title, source_lang, subtitle_kind, transcript}
      - summary_delta: {text}
      - summary: {summary}
      - chapters: {chapters}
      - key_points: {key_points}
      - done: {markdown}
      - error: {detail, status_code?}
    """
    try:
        _require_llm_key()
        yield {"event": "status", "data": {"stage": "fetching_subtitles"}}
        tr = fetch_transcript(url)
        clipped = _truncate_transcript(tr.text, SUMMARY_MAX_TRANSCRIPT_CHARS)
        yield {
            "event": "meta",
            "data": {
                "title": tr.title,
                "source_lang": tr.language,
                "subtitle_kind": tr.kind,
                "transcript": tr.text,
            },
        }

        yield {"event": "status", "data": {"stage": "generating"}}
        structure_error: Exception | None = None
        structure_result: dict[str, Any] | None = None

        with ThreadPoolExecutor(max_workers=1) as pool:
            structure_future: Future[dict[str, Any]] = pool.submit(
                _call_structure_llm, tr.title, clipped
            )

            summary_parts: list[str] = []
            for piece in _iter_stream_summary(tr.title, clipped):
                summary_parts.append(piece)
                yield {"event": "summary_delta", "data": {"text": piece}}
                # Opportunistically forward structure if already done
                if structure_result is None and structure_future.done():
                    try:
                        structure_result = structure_future.result()
                    except Exception as exc:  # noqa: BLE001
                        structure_error = exc

            summary_text = "".join(summary_parts).strip()
            if not summary_text:
                raise ServiceError("AI 未能生成整体摘要，请稍后重试", status_code=502)
            yield {"event": "summary", "data": {"summary": summary_text}}

            if structure_result is None and structure_error is None:
                try:
                    structure_result = structure_future.result(
                        timeout=SUMMARY_TIMEOUT_SECONDS
                    )
                except Exception as exc:  # noqa: BLE001
                    structure_error = exc

        chapters: list[SummaryChapter] = []
        key_points: list[SummaryKeyPoint] = []
        if structure_error is not None:
            if isinstance(structure_error, ServiceError):
                raise structure_error
            logger.exception("Structure LLM failed", exc_info=structure_error)
            raise ServiceError("章节与要点生成失败，请稍后重试", status_code=502)

        assert structure_result is not None
        chapters = _to_chapters(structure_result.get("chapters"))
        key_points = _to_key_points(structure_result.get("key_points"))
        yield {
            "event": "chapters",
            "data": {"chapters": [c.model_dump() for c in chapters]},
        }
        yield {
            "event": "key_points",
            "data": {"key_points": [k.model_dump() for k in key_points]},
        }

        md = build_markdown(tr.title, summary_text, chapters, key_points)
        yield {"event": "status", "data": {"stage": "done"}}
        yield {"event": "done", "data": {"markdown": md}}
    except ServiceError as exc:
        yield {
            "event": "error",
            "data": {"detail": exc.detail, "status_code": exc.status_code},
        }
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected stream summarize failure: %s", exc)
        yield {
            "event": "error",
            "data": {"detail": "AI 总结失败，请稍后重试", "status_code": 502},
        }
