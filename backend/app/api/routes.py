from __future__ import annotations

import concurrent.futures
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import DOWNLOAD_TIMEOUT_SECONDS
from app.schemas import (
    DownloadRequest,
    DownloadResponse,
    HealthResponse,
    ParseRequest,
    ParseResponse,
)
from app.services import ytdlp_service
from app.services.file_registry import registry
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


def _raise_service_error(exc: ServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        yt_dlp=ytdlp_service.yt_dlp_version(),
        ffmpeg=ytdlp_service.ffmpeg_available(),
    )


@router.post("/parse", response_model=ParseResponse)
def parse_video(body: ParseRequest) -> ParseResponse:
    try:
        return ytdlp_service.parse(body.url)
    except ServiceError as exc:
        _raise_service_error(exc)


@router.post("/download", response_model=DownloadResponse)
def download_video(body: DownloadRequest) -> DownloadResponse:
    if not registry.try_acquire_download_slot():
        raise HTTPException(status_code=409, detail="已有任务进行中，请稍后再试")

    media_type = body.media_type
    quality = body.quality or "best"
    format_id = body.format_id
    resolved = ytdlp_service.resolve_option_id(body.option_id)
    if resolved is not None:
        media_type, quality = resolved

    result = None
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                ytdlp_service.download,
                body.url,
                media_type,
                quality,
                format_id,
            )
            try:
                result = future.result(timeout=DOWNLOAD_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError as exc:
                raise HTTPException(
                    status_code=504,
                    detail="解析或下载超时，请稍后重试",
                ) from exc
        assert result is not None
        file_id = registry.register(
            path=result["path"],
            title=result["title"],
            ext=result["ext"],
            filename=result["filename"],
            size=result["size"],
        )
        return DownloadResponse(
            file_id=file_id,
            filename=result["filename"],
            size=result["size"],
        )
    except ServiceError as exc:
        _raise_service_error(exc)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected download failure")
        raise HTTPException(status_code=502, detail="解析或下载失败，请稍后重试") from exc
    finally:
        registry.release_download_slot()


@router.get("/files/{file_id}")
def get_file(file_id: str) -> FileResponse:
    record = registry.get(file_id)
    if record is None:
        raise HTTPException(status_code=404, detail="文件已清理，请重新下载")
    return FileResponse(
        path=record.path,
        filename=record.filename,
        media_type="application/octet-stream",
        content_disposition_type="attachment",
    )
