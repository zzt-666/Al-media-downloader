from __future__ import annotations

import logging
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError

from app.config import ALLOWED_URL_SCHEMES, DEFAULT_FORMAT, DOWNLOAD_DIR
from app.schemas import DownloadOption, MediaType, ParseResponse
from app.services.douyin_patch import apply_douyin_patch

VALID_MEDIA_TYPES: frozenset[str] = frozenset({"av", "video", "audio"})

logger = logging.getLogger(__name__)

# Douyin web API needs signed requests (see douyin_patch)
apply_douyin_patch()


class ServiceError(Exception):
    """User-facing Chinese error with optional HTTP status."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _douyin_video_id_from_url(parsed) -> Optional[str]:
    """Extract a concrete Douyin aweme/video id, or None for feed/home pages."""
    qs = parse_qs(parsed.query)
    modal_id = (qs.get("modal_id") or [None])[0]
    if modal_id and str(modal_id).isdigit():
        return str(modal_id)

    path = parsed.path or ""
    for pattern in (r"/video/(\d+)", r"/note/(\d+)", r"/share/video/(\d+)"):
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    return None


def _is_douyin_non_video_page(parsed) -> bool:
    """Homepage / recommend / feed pages cannot be parsed as a single video."""
    host = (parsed.netloc or "").lower()
    if "douyin.com" not in host:
        return False
    if _douyin_video_id_from_url(parsed):
        return False
    path = (parsed.path or "/").rstrip("/") or "/"
    # Bare site, recommend, jingxuan/discover/follow without modal_id, etc.
    if path in {"/", ""}:
        return True
    feed_prefixes = (
        "/recommend",
        "/jingxuan",
        "/discover",
        "/follow",
        "/friend",
        "/search",
        "/user",
        "/channel",
    )
    return any(path == p or path.startswith(p + "/") for p in feed_prefixes)


def normalize_media_url(url: str) -> str:
    """Rewrite share/feed URLs into extractor-friendly canonical forms."""
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    if "douyin.com" not in host:
        return url.strip()

    video_id = _douyin_video_id_from_url(parsed)
    if video_id:
        return f"https://www.douyin.com/video/{video_id}"

    return url.strip()


def validate_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw:
        raise ServiceError("请输入有效的 http(s) 视频链接")
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES or not parsed.netloc:
        raise ServiceError("请输入有效的 http(s) 视频链接")
    if _is_douyin_non_video_page(parsed):
        raise ServiceError(
            "这是抖音首页/推荐页，不是单个视频。请打开具体视频后复制链接"
            "（地址里通常有 /video/数字 或 modal_id=数字）",
            status_code=400,
        )
    return normalize_media_url(raw)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def yt_dlp_version() -> Optional[str]:
    try:
        from yt_dlp.version import __version__

        return __version__
    except Exception:  # noqa: BLE001
        return None


def _is_none_codec(codec: Any) -> bool:
    if codec is None:
        return True
    s = str(codec).lower()
    return s in {"", "none", "null"}


def _resolution_height(fmt: dict[str, Any]) -> int:
    height = fmt.get("height")
    if isinstance(height, (int, float)) and height > 0:
        return int(height)
    res = fmt.get("resolution") or fmt.get("format_note") or ""
    match = re.search(r"(\d{3,4})p", str(res), re.I)
    if match:
        return int(match.group(1))
    return 0


def _is_useless_format(fmt: dict[str, Any]) -> bool:
    format_id = str(fmt.get("format_id") or "")
    note = str(fmt.get("format_note") or "").lower()
    protocol = str(fmt.get("protocol") or "").lower()
    format_str = str(fmt.get("format") or "").lower()

    if "storyboard" in note or "storyboard" in format_str or format_id.startswith("sb"):
        return True
    if "mhtml" in str(fmt.get("ext") or "").lower():
        return True

    no_video = _is_none_codec(fmt.get("vcodec"))
    no_audio = _is_none_codec(fmt.get("acodec"))
    size = fmt.get("filesize") or fmt.get("filesize_approx") or 0
    try:
        size_i = int(size)
    except (TypeError, ValueError):
        size_i = 0

    if no_video and no_audio:
        return True
    if no_video and size_i and size_i < 20_000 and "preview" in note:
        return True
    if protocol == "mhtml":
        return True
    return False


def _has_video(fmt: dict[str, Any]) -> bool:
    return not _is_none_codec(fmt.get("vcodec"))


def _normalize_media_type(media_type: Optional[str]) -> MediaType:
    raw = (media_type or "av").strip().lower()
    if raw in VALID_MEDIA_TYPES:
        return raw  # type: ignore[return-value]
    return "av"


def _parse_quality_height(quality: Optional[str]) -> Optional[int]:
    """Return target height, or None for「最佳」."""
    raw = (quality or "best").strip().lower()
    if raw in {"", "best", "auto", "default"}:
        return None
    raw = raw.rstrip("p")
    try:
        height = int(raw)
    except ValueError:
        return None
    return height if height > 0 else None


def _filesize_of(fmt: dict[str, Any]) -> Optional[int]:
    size = fmt.get("filesize") or fmt.get("filesize_approx")
    try:
        value = int(size) if size is not None else 0
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _is_avc(fmt: dict[str, Any]) -> bool:
    v = str(fmt.get("vcodec") or "").lower()
    return v.startswith("avc") or "h264" in v


def _has_audio(fmt: dict[str, Any]) -> bool:
    return not _is_none_codec(fmt.get("acodec"))


def _is_watermarked(fmt: dict[str, Any]) -> bool:
    note = str(fmt.get("format_note") or "").lower()
    fid = str(fmt.get("format_id") or "").lower()
    return "watermark" in note or fid in {"download_addr", "download_addr_265"}


def _format_size_short(num: Optional[int]) -> Optional[str]:
    if not num:
        return None
    mb = num / (1024 ** 2)
    if mb >= 100:
        return f"{mb:.0f}MB"
    if mb >= 1:
        return f"{mb:.1f}MB"
    kb = num / 1024
    return f"{kb:.0f}KB"


def _pick_rank(fmt: dict[str, Any]) -> tuple:
    """Higher is better. Prefer non-watermarked, H.264, Direct, higher bitrate."""
    note = str(fmt.get("format_note") or "").lower()
    tbr = float(fmt.get("tbr") or 0)
    size = float(_filesize_of(fmt) or 0)
    return (
        0 if _is_watermarked(fmt) else 1,
        1 if _is_avc(fmt) else 0,
        1 if "direct" in note else 0,
        0 if "api" in note and "playback" not in note and "direct" not in note else 1,
        tbr,
        size,
    )


def _pick_best_format(group: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    usable = [f for f in group if not _is_watermarked(f)]
    pool = usable or group
    if not pool:
        return None
    return max(pool, key=_pick_rank)


def _collect_height_picks(
    raw_formats: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Optional[dict[str, Any]]]:
    """
    Returns:
      video_picks: one best format per height (desc), watermarked excluded when possible
      video_only_streams: true video-only formats (no audio)
      audio_best: best audio-only format if any
    """
    by_height: dict[int, list[dict[str, Any]]] = {}
    video_only: list[dict[str, Any]] = []
    audio_only: list[dict[str, Any]] = []

    for fmt in raw_formats or []:
        if not isinstance(fmt, dict) or _is_useless_format(fmt):
            continue
        if _is_watermarked(fmt):
            continue
        if _has_video(fmt) and _has_audio(fmt):
            height = _resolution_height(fmt)
            if height >= 240:
                by_height.setdefault(height, []).append(fmt)
        elif _has_video(fmt) and not _has_audio(fmt):
            height = _resolution_height(fmt)
            if height >= 240:
                by_height.setdefault(height, []).append(fmt)
                video_only.append(fmt)
        elif _has_audio(fmt) and not _has_video(fmt):
            audio_only.append(fmt)

    picks: list[dict[str, Any]] = []
    for height in sorted(by_height.keys(), reverse=True):
        best = _pick_best_format(by_height[height])
        if best:
            picks.append(best)

    audio_best = None
    if audio_only:
        def abr(f: dict[str, Any]) -> float:
            return float(f.get("abr") or f.get("tbr") or _filesize_of(f) or 0)

        m4a = [f for f in audio_only if str(f.get("ext") or "").lower() in {"m4a", "mp4"}]
        audio_best = max(m4a or audio_only, key=abr)

    return picks, video_only, audio_best


def build_download_options(raw_formats: list[dict[str, Any]]) -> list[DownloadOption]:
    """
    One flat list of cards — clarity + format already combined.

    - Skip watermarked junk (e.g. Douyin download_addr 405P oversized).
    - Pin concrete format_id so label size matches what we download.
    - Douyin often only has muxed A+V: 「仅视频/仅音频」still offered, stripped/extracted later.
    """
    picks, video_only_streams, audio_best = _collect_height_picks(raw_formats)
    options: list[DownloadOption] = []
    has_true_video_only = bool(video_only_streams)

    if picks:
        top = picks[0]
        top_h = _resolution_height(top)
        top_id = str(top.get("format_id") or "")
        options.append(
            DownloadOption(
                id=f"av:{top_h}",
                label=f"{top_h}P 最佳（视频+音频）",
                sublabel="MP4 · 含音频",
                media_type="av",
                quality=str(top_h),
                format_id=top_id or None,
                filesize=_filesize_of(top),
                recommended=True,
            )
        )
        for fmt in picks:
            height = _resolution_height(fmt)
            # Prefer a true video-only sibling at same height when available
            vo = None
            if has_true_video_only:
                same = [
                    f
                    for f in video_only_streams
                    if _resolution_height(f) == height
                ]
                vo = _pick_best_format(same) if same else None
            use = vo or fmt
            use_id = str(use.get("format_id") or "")
            use_size = _filesize_of(use)
            use_size_txt = _format_size_short(use_size)
            options.append(
                DownloadOption(
                    id=f"video:{height}",
                    label=(
                        f"{height}P 仅视频（{use_size_txt}）"
                        if use_size_txt
                        else f"{height}P 仅视频"
                    ),
                    sublabel="MP4 · 仅视频",
                    media_type="video",
                    quality=str(height),
                    format_id=use_id or None,
                    filesize=use_size,
                )
            )
    else:
        options.append(
            DownloadOption(
                id="av:best",
                label="最佳（视频+音频）",
                sublabel="MP4 · 含音频",
                media_type="av",
                quality="best",
                recommended=True,
            )
        )

    audio_size = _filesize_of(audio_best) if audio_best else None
    audio_size_txt = _format_size_short(audio_size)
    options.append(
        DownloadOption(
            id="audio:best",
            label=f"仅音频（{audio_size_txt}）" if audio_size_txt else "仅音频",
            sublabel="M4A · 仅音频",
            media_type="audio",
            quality="best",
            format_id=str(audio_best["format_id"]) if audio_best and audio_best.get("format_id") else None,
            filesize=audio_size,
        )
    )
    return options


def resolve_option_id(option_id: Optional[str]) -> Optional[tuple[MediaType, str]]:
    """Parse 'av:1080' / 'video:720' / 'audio:best' → (media_type, quality)."""
    raw = (option_id or "").strip()
    if not raw or ":" not in raw:
        return None
    media, quality = raw.split(":", 1)
    media = media.strip().lower()
    quality = quality.strip() or "best"
    if media not in VALID_MEDIA_TYPES:
        return None
    return media, quality  # type: ignore[return-value]


def build_format_candidates(
    quality: Optional[str] = None,
    media_type: Optional[str] = "av",
    format_id: Optional[str] = None,
) -> list[str]:
    """
    Map UI choice → yt-dlp selectors.

    When format_id is known, prefer it (exact card the user clicked).
    """
    mode = _normalize_media_type(media_type)
    height = _parse_quality_height(quality)
    pinned = (format_id or "").strip()

    if mode == "audio":
        # Douyin often has no audio-only stream — fall back to muxed then ffmpeg extract
        if pinned:
            return [pinned, "ba[ext=m4a]/ba/bestaudio", "bestaudio", "b"]
        return ["ba[ext=m4a]/ba/bestaudio", "bestaudio", "b"]

    if mode == "video":
        # Exact id first; may still be muxed (Douyin) — audio stripped after download
        if pinned:
            return [
                pinned,
                (
                    f"bv*[height={height}][ext=mp4][vcodec^=avc]/"
                    f"bv*[height={height}][vcodec^=avc]/"
                    f"bv*[height={height}]"
                    if height
                    else "bv*[ext=mp4][vcodec^=avc]/bv*"
                ),
            ]
        if height is not None:
            h = height
            return [
                (
                    f"bv*[height={h}][ext=mp4][vcodec^=avc]/"
                    f"bv*[height={h}][vcodec^=avc]/"
                    f"bv*[height<={h}][ext=mp4][vcodec^=avc]/"
                    f"bv*[height<={h}][vcodec^=avc]/"
                    f"bv*[height={h}]/bv*[height<={h}]"
                ),
                "bv*[ext=mp4][vcodec^=avc]/bv*[vcodec^=avc]/bv*/bestvideo",
            ]
        return [
            "bv*[ext=mp4][vcodec^=avc]/bv*[vcodec^=avc]/bv*/bestvideo",
            "bestvideo",
        ]

    # media_type == av
    if pinned:
        # Bilibili pins are often video-only — MUST merge audio before bare id.
        # Douyin pins are usually already muxed; bare id is the fallback.
        return [
            f"{pinned}+ba[ext=m4a]",
            f"{pinned}+ba",
            f"{pinned}+bestaudio",
            pinned,
            DEFAULT_FORMAT,
        ]
    if height is not None:
        h = height
        return [
            (
                f"bv*[height={h}][vcodec^=avc]+ba[ext=m4a]/"
                f"bv*[height={h}][vcodec^=avc]+ba/"
                f"bv*[height={h}]+ba[ext=m4a]/"
                f"bv*[height={h}]+ba/"
                # Douyin-style already-muxed progressive
                f"b[height={h}][vcodec^=avc]/"
                f"b[height={h}]/"
                f"bv*[height<={h}][vcodec^=avc]+ba/"
                f"bv*[height<={h}]+ba"
            ),
            DEFAULT_FORMAT,
        ]
    return [DEFAULT_FORMAT]


def _map_download_error(exc: BaseException) -> ServiceError:
    msg = str(exc).lower()
    raw = str(exc)
    logger.warning("yt-dlp error: %s", raw)

    if "ffmpeg" in msg or "ffprobe" in msg:
        return ServiceError("下载该内容需要本机安装 ffmpeg", status_code=400)
    if "fresh cookies" in msg or ("cookie" in msg and "douyin" in msg):
        return ServiceError(
            "抖音暂时无法解析该视频，请稍后重试或换一条链接",
            status_code=400,
        )
    if "unsupported url" in msg or "no suitable extractor" in msg or "unable to extract" in msg:
        return ServiceError(
            "暂无法识别该链接，请确认是否为 yt-dlp 支持的站点",
            status_code=400,
        )
    if any(
        x in msg
        for x in (
            "video unavailable",
            "private video",
            "has been removed",
            "not available",
            "404",
            "http error 404",
            "sign in",
            "members-only",
        )
    ):
        return ServiceError("视频不存在、已删除或无权访问", status_code=400)
    if any(x in msg for x in ("timed out", "timeout", "temporary failure", "network is unreachable")):
        return ServiceError("解析或下载超时，请稍后重试", status_code=504)
    return ServiceError("解析或下载失败，请稍后重试", status_code=502)


def _as_optional_int(value: Any) -> Optional[int]:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _format_upload_date(value: Any) -> Optional[str]:
    """yt-dlp upload_date is usually YYYYMMDD → YYYY-MM-DD."""
    raw = str(value or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return raw or None


def _clean_description(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Collapse excessive blank lines for compact 1–2 line UI preview
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def parse(url: str) -> ParseResponse:
    url = validate_url(url)
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            data = ydl.sanitize_info(info) or {}
    except DownloadError as exc:
        raise _map_download_error(exc) from exc
    except Exception as exc:  # noqa: BLE001
        raise _map_download_error(exc) from exc

    if data.get("_type") == "playlist":
        entries = data.get("entries") or []
        if entries:
            data = entries[0] if isinstance(entries[0], dict) else data

    options = build_download_options(data.get("formats") or [])
    if not options:
        raise ServiceError("暂无可用下载选项，请更换链接或稍后重试", status_code=400)

    video_id = str(data.get("id") or "")
    title = str(data.get("title") or "未命名视频")
    if not video_id:
        raise ServiceError("暂无法识别该链接，请确认是否为 yt-dlp 支持的站点")

    return ParseResponse(
        id=video_id,
        title=title,
        thumbnail=data.get("thumbnail"),
        duration=data.get("duration"),
        uploader=data.get("uploader"),
        webpage_url=data.get("webpage_url") or url,
        extractor=data.get("extractor"),
        extractor_key=data.get("extractor_key"),
        view_count=_as_optional_int(data.get("view_count")),
        like_count=_as_optional_int(data.get("like_count")),
        upload_date=_format_upload_date(data.get("upload_date")),
        description=_clean_description(data.get("description")),
        options=options,
    )


def _safe_filename(title: str, ext: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .") or "video"
    cleaned = cleaned[:120]
    ext = (ext or "mp4").lstrip(".")
    return f"{cleaned}.{ext}"


def _resolve_filepath(info: dict[str, Any], ydl: yt_dlp.YoutubeDL) -> Path:
    requested = info.get("requested_downloads") or []
    if requested and isinstance(requested[0], dict):
        fp = requested[0].get("filepath")
        if fp:
            path = Path(fp)
            if path.is_file():
                return path

    for key in ("filepath", "_filename"):
        fp = info.get(key)
        if fp:
            path = Path(fp)
            if path.is_file():
                return path

    try:
        prepared = ydl.prepare_filename(info)
        path = Path(prepared)
        if path.is_file():
            return path
        for candidate in path.parent.glob(path.stem + ".*"):
            if candidate.is_file() and candidate.suffix.lower() not in {
                ".json",
                ".description",
                ".jpg",
                ".webp",
                ".png",
            }:
                return candidate
    except Exception:  # noqa: BLE001
        pass

    raise ServiceError("下载完成但未找到输出文件，请重试", status_code=502)


def _normalize_entry(data: dict[str, Any]) -> dict[str, Any]:
    if data.get("_type") == "playlist":
        entries = data.get("entries") or []
        if entries and isinstance(entries[0], dict):
            return entries[0]
    return data


def _mp4_needs_remux(path: Path) -> bool:
    """YouTube video-only often ships as fragmented DASH MP4 (ftypdash)."""
    try:
        head = path.read_bytes()[:64]
    except OSError:
        return False
    # e.g. ....ftypdash — rejected by many stock players
    return b"ftypdash" in head or b"dash" in head[4:16]


def _remux_mp4_for_players(path: Path) -> Path:
    """
    Remux MP4 with stream copy + faststart so Windows/macOS players can open it.
    No re-encode; safe for Bilibili progressive MP4 as well (skipped unless needed).
    """
    if not ffmpeg_available():
        logger.warning("ffmpeg missing; cannot remux DASH MP4 for compatibility")
        return path
    if path.suffix.lower() not in {".mp4", ".m4v", ".mov"}:
        return path
    if not _mp4_needs_remux(path):
        return path

    tmp = path.with_name(f"{path.stem}_compat{path.suffix}")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("mp4 remux failed path=%s err=%s", path, exc)
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        return path

    if not tmp.is_file() or tmp.stat().st_size <= 0:
        tmp.unlink(missing_ok=True)
        return path

    try:
        path.unlink(missing_ok=True)
        tmp.replace(path)
    except OSError as exc:
        logger.warning("mp4 remux replace failed err=%s", exc)
        return tmp if tmp.is_file() else path
    return path


def _ffprobe_stream_types(path: Path) -> set[str]:
    try:
        raw = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                str(path),
            ],
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return set()
    return {line.strip() for line in raw.splitlines() if line.strip()}


def _strip_audio_track(path: Path) -> Path:
    """Remove audio so「仅视频」is truly silent (needed for Douyin muxed MP4)."""
    if not ffmpeg_available():
        return path
    types = _ffprobe_stream_types(path)
    if "audio" not in types:
        return path
    tmp = path.with_name(f"{path.stem}_silent{path.suffix or '.mp4'}")
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-c:v",
        "copy",
        "-an",
        "-movflags",
        "+faststart",
        str(tmp),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        logger.warning("strip audio failed path=%s err=%s", path, exc)
        tmp.unlink(missing_ok=True)
        return path
    if not tmp.is_file() or tmp.stat().st_size <= 0:
        tmp.unlink(missing_ok=True)
        return path
    path.unlink(missing_ok=True)
    tmp.replace(path)
    return path


def _extract_audio_track(path: Path) -> Path:
    """Extract audio from muxed file when site has no audio-only formats."""
    if not ffmpeg_available():
        return path
    types = _ffprobe_stream_types(path)
    if "audio" not in types:
        return path
    out = path.with_name(f"{path.stem}_audio.m4a")
    for audio_args in (["-c:a", "copy"], ["-c:a", "aac", "-b:a", "192k"]):
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-vn",
            *audio_args,
            str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            if out.is_file() and out.stat().st_size > 0:
                path.unlink(missing_ok=True)
                return out
        except (OSError, subprocess.CalledProcessError):
            out.unlink(missing_ok=True)
            continue
    return path


def _download_with_format(
    url: str,
    fmt: str,
    media_type: MediaType = "av",
) -> tuple[dict[str, Any], Path]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "noplaylist": True,
        "format": fmt,
        "outtmpl": str(DOWNLOAD_DIR / "%(id)s_%(format_id)s.%(ext)s"),
        "paths": {"home": str(DOWNLOAD_DIR)},
        "restrictfilenames": True,
        "overwrites": True,
        "socket_timeout": 120,
        "retries": 5,
        "fragment_retries": 5,
    }
    if media_type == "av" or "+" in fmt:
        opts["merge_output_format"] = "mp4"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        data = _normalize_entry(ydl.sanitize_info(info) or {})
        path = _resolve_filepath(data if isinstance(data, dict) else {}, ydl)
        if media_type == "video":
            path = _remux_mp4_for_players(path)
            path = _strip_audio_track(path)
        elif media_type == "audio":
            # Muxed progressive (common on Douyin): extract audio track
            types = _ffprobe_stream_types(path)
            if "video" in types and "audio" in types:
                path = _extract_audio_track(path)
        elif media_type == "av":
            # Guard: never accept silent file as「视频+音频」(Bilibili video-only pin)
            types = _ffprobe_stream_types(path)
            if "audio" not in types or "video" not in types:
                raise DownloadError(
                    f"Output missing audio/video for av download (streams={sorted(types)})"
                )
        return data, path


def download(
    url: str,
    media_type: Optional[str] = "av",
    quality: Optional[str] = "best",
    format_id: Optional[str] = None,
) -> dict[str, Any]:
    """Download by media_type + quality (+ optional pinned format_id)."""
    url = validate_url(url)
    mode = _normalize_media_type(media_type)
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    candidates = build_format_candidates(quality, mode, format_id)
    last_error: Optional[BaseException] = None

    for fmt in candidates:
        try:
            data, path = _download_with_format(url, fmt, mode)
            title = str(data.get("title") or "video")
            default_ext = "m4a" if mode == "audio" else "mp4"
            ext = path.suffix.lstrip(".") or str(data.get("ext") or default_ext)
            filename = _safe_filename(title, ext)
            return {
                "path": path,
                "title": title,
                "ext": ext,
                "filename": filename,
                "size": path.stat().st_size,
            }
        except ServiceError:
            raise
        except DownloadError as exc:
            last_error = exc
            logger.warning(
                "download candidate failed format=%s media=%s quality=%s err=%s",
                fmt,
                mode,
                quality,
                exc,
            )
            continue
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "download candidate failed format=%s media=%s quality=%s err=%s",
                fmt,
                mode,
                quality,
                exc,
            )
            continue

    if last_error is not None:
        raise _map_download_error(last_error)
    raise ServiceError("解析或下载失败，请稍后重试", status_code=502)
