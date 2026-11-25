"""Summary feature extensions: mindmap + AI chat.

Mounted alongside core routes without modifying summarize endpoints.
"""

from __future__ import annotations

import concurrent.futures
import logging
from collections.abc import Iterator
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.config import SUMMARY_TIMEOUT_SECONDS
from app.schemas import ChatStreamRequest, MindmapRequest, MindmapResponse
from app.services.chat_service import iter_chat_events
from app.services.mindmap_service import generate_mindmap
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/summarize/mindmap", response_model=MindmapResponse)
def summarize_mindmap(body: MindmapRequest) -> MindmapResponse:
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(generate_mindmap, body)
            try:
                return future.result(timeout=SUMMARY_TIMEOUT_SECONDS + 30)
            except concurrent.futures.TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="思维导图生成超时，请稍后重试",
                ) from exc
    except ServiceError as exc:
        _raise_service_error(exc)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected mindmap failure")
        raise HTTPException(status_code=502, detail="思维导图生成失败，请稍后重试") from exc


@router.post("/summarize/chat/stream", response_class=EventSourceResponse)
def summarize_chat_stream(body: ChatStreamRequest) -> Iterator[ServerSentEvent]:
    for item in iter_chat_events(body):
        event = str(item.get("event") or "message")
        data: Any = item.get("data")
        yield ServerSentEvent(event=event, data=data)
