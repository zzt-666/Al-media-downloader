from __future__ import annotations

import logging
import re
import shutil
import subprocess
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urljoin, urlparse

import yt_dlp
from yt_dlp.utils import DownloadError

from app.config import ALLOWED_URL_SCHEMES, DEFAULT_FORMAT, DOWNLOAD_DIR
from app.schemas import DownloadOption, MediaType, ParseResponse
from app.services.douyin_patch import apply_douyin_patch

VALID_MEDIA_TYPES: frozenset[str] = frozenset({"av", "video", "audio"})

# Share short-links (v.douyin.com/xxxx) need HTTP redirect expand before yt-dlp.
DOUYIN_SHORT_HOSTS = frozenset({"v.douyin.com"})
# Synthetic AV for Douyin image/notes (images + music → MP4 via ffmpeg).
NOTE_AV_FORMAT_ID = "__douyin_note_av__"
_DOUYIN_REDIRECT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

logger = logging.getLogger(__name__)

# Douyin web API needs signed requests (see douyin_patch)
apply_douyin_patch()


class ServiceError(Exception):
    """User-facing Chinese error with optional HTTP status."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def _is_douyin_family_host(host: str) -> bool:
    host = (host or "").lower()
    return "douyin.com" in host or "iesdouyin.com" in host


def _douyin_video_id_from_url(parsed) -> Optional[str]:
    """Extract a concrete Douyin aweme/video id, or None for feed/home pages."""
    qs = parse_qs(parsed.query)
    modal_id = (qs.get("modal_id") or [None])[0]
    if modal_id and str(modal_id).isdigit():
        return str(modal_id)

    path = parsed.path or ""
    for pattern in (
        r"/video/(\d+)",
        r"/note/(\d+)",
        r"/share/video/(\d+)",
        r"/share/note/(\d+)",
    ):
        match = re.search(pattern, path)
        if match:
            return match.group(1)
    return None


def _resolve_http_redirects(url: str, max_hops: int = 8) -> str:
    """Follow Douyin share short-link redirects without downloading bodies."""

    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
            return None

    current = url
    opener = urllib.request.build_opener(_NoRedirect)
    headers = {
        "User-Agent": _DOUYIN_REDIRECT_UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    for _ in range(max_hops):
        req = urllib.request.Request(current, headers=headers, method="GET")
        try:
            with opener.open(req, timeout=15) as resp:
                return resp.geturl() or current
        except urllib.error.HTTPError as exc:
            loc = exc.headers.get("Location") if exc.headers else None
            if loc and exc.code in {301, 302, 303, 307, 308}:
                current = urljoin(current, loc)
                # Stop early once we already have a concrete aweme id.
                if _douyin_video_id_from_url(urlparse(current)):
                    return current
                continue
            return current
        except Exception as exc:  # noqa: BLE001
            logger.warning("Douyin redirect resolve failed url=%s err=%s", url, exc)
            return current
    return current


def _is_douyin_non_video_page(parsed) -> bool:
    """Homepage / recommend / feed pages cannot be parsed as a single video."""
    host = (parsed.netloc or "").lower()
    if not _is_douyin_family_host(host):
        return False
    # Short share links are resolvable; do not reject them here.
    if host in DOUYIN_SHORT_HOSTS:
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
    """Rewrite share/feed/short URLs into extractor-friendly canonical forms."""
    raw = url.strip()
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if not _is_douyin_family_host(host):
        return raw

    video_id = _douyin_video_id_from_url(parsed)
    # v.douyin.com/xxxx → follow redirects → /note|/video|/share/...
    if not video_id and host in DOUYIN_SHORT_HOSTS:
        resolved = _resolve_http_redirects(raw)
        if resolved != raw:
            logger.info("Resolved Douyin short URL %s → %s", raw, resolved)
        parsed = urlparse(resolved)
        host = (parsed.netloc or "").lower()
        if not _is_douyin_family_host(host):
            return resolved
        video_id = _douyin_video_id_from_url(parsed)
        raw = resolved

    if video_id:
        return f"https://www.douyin.com/video/{video_id}"

    if host in DOUYIN_SHORT_HOSTS:
        raise ServiceError(
            "无法从抖音短链接解析出视频，请打开视频后复制含 /video/数字 的完整链接",
            status_code=400,
        )

    return raw


def _is_pure_http_url(value: str) -> bool:
    """True when the whole string is already a single http(s) URL."""
    parsed = urlparse(value)
    return parsed.scheme.lower() in ALLOWED_URL_SCHEMES and bool(parsed.netloc)


def _extract_http_url_from_text(text: str) -> Optional[str]:
    """
    Pull the first http(s) URL out of share-copy text (Douyin / Bilibili / etc.).

    Only used when the full input is not already a pure URL, so existing
    pure-link behavior is unchanged.
    """
    match = re.search(r"https?://[^\s<>\"']+", text, flags=re.IGNORECASE)
    if not match:
        return None
    candidate = match.group(0).rstrip("，。；：、！？,.!?;:)]}＞》」』\"'")
    # Guard against trailing junk glued by some share apps (e.g. …/xxx/DhB:/)
    # Keep path segments that look like short-ids; strip only if clearly broken.
    if not _is_pure_http_url(candidate):
        return None
    return candidate


def coerce_media_url(url: str) -> str:
    """
    Accept either a pure http(s) URL or share text that contains one.

    Priority:
      1) whole input is already a pure URL
      2) else extract the first http(s) URL from the text
      3) else raise a Chinese validation error
    """
    raw = (url or "").strip()
    if not raw:
        raise ServiceError("请输入有效的 http(s) 视频链接")
    if _is_pure_http_url(raw):
        return raw
    extracted = _extract_http_url_from_text(raw)
    if extracted:
        logger.info("Extracted media URL from share text → %s", extracted)
        return extracted
    raise ServiceError("请输入有效的 http(s) 视频链接")


def validate_url(url: str) -> str:
    raw = coerce_media_url(url)
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


def _http_download_file(url: str, dest: Path, referer: str = "https://www.douyin.com/") -> None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": _DOUYIN_REDIRECT_UA,
            "Referer": referer,
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        dest.write_bytes(resp.read())
    if not dest.is_file() or dest.stat().st_size <= 0:
        raise ServiceError("图文素材下载失败，请稍后重试", status_code=502)


def probe_douyin_note_bundle(aweme_id: str) -> Optional[dict[str, Any]]:
    """
    Detect Douyin image/note posts that have images + music but no real video stream.

    Important: some notes expose play_addr as audio/mp4 while yt-dlp still labels it
    as h264「Direct video」with a fake height. Trust images + empty bit_rate instead
    of play_addr URI heuristics.
    """
    from yt_dlp.extractor.tiktok import DouyinIE

    from app.services.douyin_patch import _check_and_get_required_cookies, _get_aweme_detail

    aweme_id = str(aweme_id or "").strip()
    if not aweme_id.isdigit():
        return None

    ydl = yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "noprogress": True})
    ie = DouyinIE(ydl)
    try:
        _check_and_get_required_cookies(ie)
        detail = _get_aweme_detail(ie, aweme_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("probe Douyin note failed id=%s err=%s", aweme_id, exc)
        return None
    if not detail:
        return None

    video_info = detail.get("video") or {}
    images = detail.get("images") or []
    bit_rate = video_info.get("bit_rate") or []
    # Real videos expose bitrate ladder; image notes have images and no bit_rate.
    if not images or bit_rate:
        return None

    image_urls: list[str] = []
    for im in images:
        if not isinstance(im, dict):
            continue
        urls = im.get("download_url_list") or im.get("url_list") or []
        if urls:
            image_urls.append(str(urls[0]))

    music = detail.get("music") or {}
    play = music.get("play_url") or {}
    audio_url = None
    if isinstance(play, dict):
        audio_url = (play.get("url_list") or [None])[0] or play.get("uri")
    elif isinstance(play, str):
        audio_url = play
    # Newer notes often put AAC in video.play_addr (audio/mp4), not music.play_url.
    if not audio_url:
        pa = video_info.get("play_addr") or {}
        if isinstance(pa, dict):
            audio_url = (pa.get("url_list") or [None])[0] or pa.get("uri")

    if not image_urls or not audio_url:
        return None

    duration = music.get("duration") or detail.get("duration") or 0
    try:
        duration_i = int(duration)
    except (TypeError, ValueError):
        duration_i = 0
    if duration_i <= 0:
        duration_i = 15

    return {
        "aweme_id": aweme_id,
        "image_urls": image_urls,
        "audio_url": str(audio_url),
        "duration": duration_i,
        "title": str(detail.get("desc") or aweme_id),
    }


def synthesize_douyin_note_av(bundle: dict[str, Any], out_path: Path) -> Path:
    """Compose first image + music into a playable MP4 (still-image video)."""
    if not ffmpeg_available():
        raise ServiceError("下载该内容需要本机安装 ffmpeg", status_code=400)

    work = out_path.parent / f"_note_work_{out_path.stem}"
    if work.exists():
        shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True, exist_ok=True)
    try:
        img_path = work / "cover.jpg"
        audio_path = work / "audio.mp3"
        _http_download_file(bundle["image_urls"][0], img_path)
        _http_download_file(bundle["audio_url"], audio_path)
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(img_path),
            "-i",
            str(audio_path),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-shortest",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            logger.warning("note AV synth failed err=%s", exc)
            raise ServiceError("图文合成视频失败，请稍后重试或选择仅音频", status_code=502) from exc
        if not out_path.is_file() or out_path.stat().st_size <= 0:
            raise ServiceError("图文合成视频失败，请稍后重试或选择仅音频", status_code=502)
        return out_path
    finally:
        shutil.rmtree(work, ignore_errors=True)


def build_download_options(
    raw_formats: list[dict[str, Any]],
    *,
    note_bundle: Optional[dict[str, Any]] = None,
) -> list[DownloadOption]:
    """
    One flat list of cards — clarity + format already combined.

    - Skip watermarked junk (e.g. Douyin download_addr 405P oversized).
    - Pin concrete format_id so label size matches what we download.
    - Douyin often only has muxed A+V: 「仅视频/仅音频」still offered, stripped/extracted later.
    - Douyin image/notes: offer synthetic AV (image + music → MP4) when probe finds assets.
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
    elif note_bundle:
        options.append(
            DownloadOption(
                id="av:best",
                label="最佳（视频+音频）",
                sublabel="MP4 · 图文合成",
                media_type="av",
                quality="best",
                format_id=NOTE_AV_FORMAT_ID,
                recommended=True,
            )
        )

    # Always offer「仅音频」when we have anything downloadable.
    # Douyin real videos are often muxed A+V only (no separate audio-only format);
    # download() will extract audio via ffmpeg / ba selectors in that case.
    if audio_best or picks or note_bundle:
        audio_size = _filesize_of(audio_best) if audio_best else None
        audio_size_txt = _format_size_short(audio_size)
        audio_ext = (
            str(audio_best.get("ext") or "m4a").lstrip(".").upper()
            if audio_best
            else "M4A"
        )
        options.append(
            DownloadOption(
                id="audio:best",
                label=f"仅音频（{audio_size_txt}）" if audio_size_txt else "仅音频",
                sublabel=f"{audio_ext} · 仅音频",
                media_type="audio",
                quality="best",
                format_id=(
                    str(audio_best["format_id"])
                    if audio_best and audio_best.get("format_id")
                    else None
                ),
                filesize=audio_size,
                recommended=not bool(picks) and not bool(note_bundle),
            )
        )
    elif not picks and not note_bundle:
        # Last-resort AV selector only when engine reported neither video nor audio tracks.
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

    return options


def parse_notice_for_options(
    options: list[DownloadOption],
    *,
    note_bundle: Optional[dict[str, Any]] = None,
) -> Optional[str]:
    """User-facing hint when parse succeeded but content is not a normal video."""
    if note_bundle:
        n_img = len(note_bundle.get("image_urls") or [])
        extra = f"（共 {n_img} 张图，合成时使用首图）" if n_img > 1 else ""
        return f"该链接为图文笔记，将用图片+音频合成为可播放视频{extra}"
    has_video_opt = any(o.media_type in {"av", "video"} for o in options)
    has_audio_opt = any(o.media_type == "audio" for o in options)
    if not has_video_opt and has_audio_opt:
        return "该链接没有可下载的视频轨，仅可下载音频"
    return None


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
    if "missing audio/video" in msg or "output missing" in msg:
        return ServiceError(
            "该内容没有可下载的视频（可能是图文笔记），请选择「仅音频」或更换链接",
            status_code=400,
        )
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

    raw_formats = data.get("formats") or []
    video_id = str(data.get("id") or "")
    title = str(data.get("title") or "未命名视频")
    if not video_id:
        raise ServiceError("暂无法识别该链接，请确认是否为 yt-dlp 支持的站点")

    note_bundle = None
    if _is_douyin_family_host(urlparse(url).netloc):
        note_bundle = probe_douyin_note_bundle(video_id)

    # Image notes: ignore yt-dlp's mislabeled play_addr "1080p video" formats.
    if note_bundle:
        options = build_download_options([], note_bundle=note_bundle)
    else:
        options = build_download_options(raw_formats, note_bundle=None)
    if not options:
        raise ServiceError("暂无可用下载选项，请更换链接或稍后重试", status_code=400)

    # Prefer music duration for image notes when engine duration is empty/0.
    duration = data.get("duration")
    if note_bundle and (not duration or float(duration) <= 0):
        duration = float(note_bundle["duration"])

    return ParseResponse(
        id=video_id,
        title=title,
        thumbnail=data.get("thumbnail"),
        duration=duration,
        uploader=data.get("uploader"),
        webpage_url=data.get("webpage_url") or url,
        extractor=data.get("extractor"),
        extractor_key=data.get("extractor_key"),
        view_count=_as_optional_int(data.get("view_count")),
        like_count=_as_optional_int(data.get("like_count")),
        upload_date=_format_upload_date(data.get("upload_date")),
        description=_clean_description(data.get("description")),
        notice=parse_notice_for_options(options, note_bundle=note_bundle),
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
            types = _ffprobe_stream_types(path)
            # Douyin image-notes may ship audio/mp4 labeled as play_addr video.
            if "video" not in types:
                raise DownloadError(
                    f"Output missing audio/video for video download (streams={sorted(types)})"
                )
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


def _try_download_douyin_note_av(url: str) -> Optional[dict[str, Any]]:
    """If URL is a Douyin image/note, synthesize MP4 from image + music."""
    aweme_id = _douyin_video_id_from_url(urlparse(url))
    if not aweme_id:
        return None
    bundle = probe_douyin_note_bundle(aweme_id)
    if not bundle:
        return None
    out_path = DOWNLOAD_DIR / f"{aweme_id}_note_av.mp4"
    synthesize_douyin_note_av(bundle, out_path)
    title = str(bundle.get("title") or aweme_id)
    filename = _safe_filename(title, "mp4")
    return {
        "path": out_path,
        "title": title,
        "ext": "mp4",
        "filename": filename,
        "size": out_path.stat().st_size,
    }


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

    pinned = (format_id or "").strip()
    # Douyin image/notes: synthesize before trusting mislabeled play_addr formats.
    if mode in {"av", "video"} and _is_douyin_family_host(urlparse(url).netloc):
        note_result = _try_download_douyin_note_av(url)
        if note_result is not None:
            return note_result
        if pinned == NOTE_AV_FORMAT_ID:
            raise ServiceError("图文合成视频失败，请稍后重试或选择仅音频", status_code=502)

    candidates = build_format_candidates(
        quality,
        mode,
        None if pinned == NOTE_AV_FORMAT_ID else format_id,
    )
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

    # Fallback: Douyin image/note → synthesize AV after normal selectors fail.
    if mode == "av" and _is_douyin_family_host(urlparse(url).netloc):
        result = _try_download_douyin_note_av(url)
        if result is not None:
            return result

    if last_error is not None:
        raise _map_download_error(last_error)
    raise ServiceError("解析或下载失败，请稍后重试", status_code=502)
