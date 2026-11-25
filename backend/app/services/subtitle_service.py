from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

import yt_dlp
from yt_dlp.utils import DownloadError

from app.config import SUBS_DIR
from app.services.ytdlp_service import ServiceError, validate_url

logger = logging.getLogger(__name__)

# Prefer Simplified Chinese, then other zh, then English, then anything else.
_LANG_PRIORITY: tuple[str, ...] = (
    "zh-Hans",
    "zh-CN",
    "zh-Hans-en",
    "zh",
    "ai-zh",
    "zh-Hant",
    "zh-TW",
    "zh-HK",
    "en",
    "en-US",
    "en-GB",
    "ai-en",
)

# Bilibili "danmaku" is bullet comments, not captions — never treat as transcript.
_SKIP_SUB_LANGS = frozenset({"danmaku", "danmaku_ascii"})

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


@dataclass
class TranscriptResult:
    title: str
    language: str
    kind: str  # manual | auto
    text: str  # lines like "[01:21] ..."


def _score_lang(lang: str) -> tuple[int, str]:
    """Lower score = higher priority."""
    lang_l = (lang or "").strip()
    try:
        idx = _LANG_PRIORITY.index(lang_l)
        return (idx, lang_l)
    except ValueError:
        pass
    lower = lang_l.lower()
    if lower.startswith("zh"):
        return (50, lang_l)
    if lower.startswith("en"):
        return (80, lang_l)
    return (200, lang_l)


def _pick_track(
    tracks: dict[str, Any],
) -> Optional[tuple[str, list[dict[str, Any]]]]:
    if not tracks:
        return None
    ranked = sorted(tracks.items(), key=lambda kv: _score_lang(str(kv[0])))
    for lang, formats in ranked:
        lang_s = str(lang)
        if lang_s.lower() in _SKIP_SUB_LANGS:
            continue
        if isinstance(formats, list) and formats:
            return lang_s, formats
    return None


def _pick_format_entry(formats: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    preferred_ext = ("vtt", "srt", "ttml", "srv3", "json3", "srv1", "srv2")
    by_ext = {str(f.get("ext") or "").lower(): f for f in formats if isinstance(f, dict)}
    for ext in preferred_ext:
        if ext in by_ext:
            return by_ext[ext]
    return formats[-1] if formats else None


def _fetch_bytes(url: str, timeout: int = 45) -> bytes:
    """Download subtitle bytes; prefer curl_cffi impersonation when available."""
    headers = {
        "User-Agent": _UA,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.youtube.com/",
    }
    last_exc: Exception | None = None
    try:
        from curl_cffi import requests as crequests  # type: ignore

        for impersonate in ("chrome131", "chrome124", "chrome120", "chrome"):
            try:
                resp = crequests.get(
                    url,
                    impersonate=impersonate,
                    timeout=timeout,
                    headers=headers,
                )
                if resp.status_code == 429:
                    last_exc = RuntimeError("HTTP 429 Too Many Requests")
                    continue
                if resp.status_code >= 400:
                    last_exc = RuntimeError(f"HTTP {resp.status_code}")
                    continue
                if resp.content:
                    return resp.content
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                continue
    except ImportError:
        pass

    try:
        req = Request(url, headers=headers)
        with urlopen(req, timeout=timeout) as resp:  # noqa: S310 — http(s) from yt-dlp
            return resp.read()
    except Exception as exc:  # noqa: BLE001
        if last_exc is not None:
            raise last_exc from exc
        raise


def _ms_to_stamp(ms: float) -> str:
    total = max(0, int(ms // 1000))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def _parse_clock(value: str) -> Optional[float]:
    """Parse VTT/SRT clock → milliseconds."""
    value = value.strip().replace(",", ".")
    parts = value.split(":")
    try:
        if len(parts) == 3:
            h, m, s = parts
            return (int(h) * 3600 + int(m) * 60 + float(s)) * 1000
        if len(parts) == 2:
            m, s = parts
            return (int(m) * 60 + float(s)) * 1000
    except ValueError:
        return None
    return None


def _clean_caption_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\{[^}]+\}", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_vtt_or_srt(raw: str) -> str:
    lines_out: list[str] = []
    blocks = re.split(r"\n\s*\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    time_re = re.compile(
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
        r"\s*-->\s*"
        r"(\d{1,2}:\d{2}:\d{2}[.,]\d{1,3}|\d{1,2}:\d{2}[.,]\d{1,3})"
    )
    for block in blocks:
        block = block.strip()
        if not block or block.upper().startswith("WEBVTT") or block.startswith("NOTE"):
            continue
        match = time_re.search(block)
        if not match:
            continue
        start_ms = _parse_clock(match.group(1))
        if start_ms is None:
            continue
        body_lines = []
        after = block[match.end() :].strip().split("\n")
        for line in after:
            line = line.strip()
            if not line or line.isdigit():
                continue
            cleaned = _clean_caption_text(line)
            if cleaned:
                body_lines.append(cleaned)
        if not body_lines:
            continue
        stamp = _ms_to_stamp(start_ms)
        text = " ".join(body_lines)
        # Skip near-duplicate consecutive lines (common in auto-subs)
        if lines_out and lines_out[-1].endswith(text):
            continue
        lines_out.append(f"[{stamp}] {text}")
    return "\n".join(lines_out)


def parse_json3(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return ""
    # Bilibili AI / CC JSON: {"body":[{"from":0,"to":1.2,"content":"..."}]}
    body = data.get("body")
    if isinstance(body, list) and body:
        lines_out: list[str] = []
        for item in body:
            if not isinstance(item, dict):
                continue
            content = _clean_caption_text(str(item.get("content") or ""))
            if not content:
                continue
            try:
                start_ms = float(item.get("from") or 0) * 1000
            except (TypeError, ValueError):
                start_ms = 0
            lines_out.append(f"[{_ms_to_stamp(start_ms)}] {content}")
        if lines_out:
            return "\n".join(lines_out)
    events = data.get("events") or []
    lines_out = []
    for ev in events:
        if not isinstance(ev, dict):
            continue
        segs = ev.get("segs")
        if not segs:
            continue
        start_ms = float(ev.get("tStartMs") or 0)
        text = _clean_caption_text("".join(str(s.get("utf8") or "") for s in segs if isinstance(s, dict)))
        if not text or text == "\n":
            continue
        lines_out.append(f"[{_ms_to_stamp(start_ms)}] {text}")
    return "\n".join(lines_out)


def _http_json(url: str, timeout: int = 20) -> dict[str, Any]:
    req = Request(
        url,
        headers={
            "User-Agent": _UA,
            "Referer": "https://www.bilibili.com",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _normalize_bilibili_sub_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def _is_bilibili_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return "bilibili.com" in host or host.endswith("b23.tv")


def _is_youtube_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return (
        "youtube.com" in host
        or "youtu.be" in host
        or "youtube-nocookie.com" in host
    )


def _is_douyin_url(url: str) -> bool:
    host = (urlparse(url).netloc or "").lower()
    return "douyin.com" in host or "iesdouyin.com" in host


def _youtube_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    host = (parsed.netloc or "").lower()
    path = parsed.path or ""
    if "youtu.be" in host:
        vid = path.strip("/").split("/")[0]
        return vid or None
    m = re.search(r"/(?:shorts|embed|live|v)/([\w-]{6,})", path)
    if m:
        return m.group(1)
    q = parse_qs(parsed.query)
    if q.get("v"):
        return q["v"][0]
    return None


def fetch_youtube_transcript(url: str, title_hint: str = "") -> Optional[TranscriptResult]:
    """
    YouTube fallback via youtube-transcript-api.

    yt-dlp often lists automatic_captions but timedtext CDN returns HTTP 429
    (especially after many requests / without browser impersonation). This path
    uses the public transcript endpoint that works more reliably.
    """
    if not _is_youtube_url(url):
        return None
    video_id = _youtube_video_id(url)
    if not video_id:
        return None
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        logger.warning("youtube-transcript-api not installed")
        return None

    preferred = ("zh-Hans", "zh-CN", "zh", "zh-Hant", "en", "en-US", "en-GB")
    try:
        api = YouTubeTranscriptApi()
        fetched = None
        lang = "en"
        kind = "auto"
        try:
            fetched = api.fetch(video_id, languages=list(preferred))
            # fetch() picks best match; language_code available on result in v1.x
            lang = getattr(fetched, "language_code", None) or "en"
            kind = "auto" if getattr(fetched, "is_generated", True) else "manual"
        except Exception:
            listing = api.list(video_id)
            # Prefer generated/manual in preferred order
            chosen = None
            for want in preferred:
                for tr in listing:
                    if tr.language_code == want or tr.language_code.startswith(want):
                        chosen = tr
                        break
                if chosen is not None:
                    break
            if chosen is None:
                chosen = next(iter(listing), None)
            if chosen is None:
                return None
            fetched = chosen.fetch()
            lang = chosen.language_code
            kind = "auto" if chosen.is_generated else "manual"

        lines_out: list[str] = []
        for snip in fetched:
            text = _clean_caption_text(str(getattr(snip, "text", "") or ""))
            if not text:
                continue
            start = float(getattr(snip, "start", 0) or 0)
            lines_out.append(f"[{_ms_to_stamp(start * 1000)}] {text}")
        if not lines_out:
            return None
        return TranscriptResult(
            title=title_hint or f"YouTube {video_id}",
            language=lang,
            kind=kind,
            text="\n".join(lines_out),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("youtube-transcript-api fallback failed: %s", exc)
        return None


def _pick_bilibili_subtitle_track(
    tracks: list[dict[str, Any]],
) -> Optional[tuple[str, str, str]]:
    """Return (lang, kind, subtitle_url) or None."""
    usable: list[tuple[tuple[int, str], str, str, str]] = []
    for item in tracks:
        if not isinstance(item, dict):
            continue
        lang = str(item.get("lan") or "").strip()
        sub_url = _normalize_bilibili_sub_url(
            str(item.get("subtitle_url") or item.get("subtitle_url_v2") or "")
        )
        if not lang or not sub_url.startswith("http"):
            continue
        # type 1 ≈ AI auto; type 0 ≈ uploaded/CC
        kind = "auto" if int(item.get("type") or 0) == 1 or lang.startswith("ai-") else "manual"
        usable.append((_score_lang(lang), lang, kind, sub_url))
    if not usable:
        return None
    usable.sort(key=lambda row: row[0])
    _, lang, kind, sub_url = usable[0]
    return lang, kind, sub_url


def fetch_bilibili_transcript(url: str, title_hint: str = "") -> Optional[TranscriptResult]:
    """
    Bilibili anonymous subtitle fallback via /x/v2/dm/view.

    Player APIs (/x/player/v2, /x/player/wbi/v2) often set need_login_subtitle=true and
    return an empty list when logged out — while the page still shows AI/CC captions.
    dm/view exposes the same subtitle block without that gate.
    """
    if not _is_bilibili_url(url):
        return None
    try:
        # Resolve bvid / aid / cid
        bvid = None
        m = re.search(r"(BV[\w]+)", url, flags=re.IGNORECASE)
        if m:
            bvid = m.group(1)
        if not bvid:
            return None
        view = _http_json(f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}")
        # NOTE: do not use `code or -1` — code 0 is success and is falsy in Python
        if view.get("code") != 0:
            logger.info("Bilibili view API failed: %s", view.get("message"))
            return None
        vdata = view.get("data") or {}
        aid = vdata.get("aid")
        cid = vdata.get("cid")
        title = str(vdata.get("title") or title_hint or "未命名视频")
        if not aid or not cid:
            return None

        dm = _http_json(
            f"https://api.bilibili.com/x/v2/dm/view?aid={aid}&oid={cid}&type=1"
        )
        if dm.get("code") != 0:
            logger.info("Bilibili dm/view failed: %s", dm.get("message"))
            return None
        tracks = ((dm.get("data") or {}).get("subtitle") or {}).get("subtitles") or []
        if not isinstance(tracks, list) or not tracks:
            return None
        picked = _pick_bilibili_subtitle_track(tracks)
        if picked is None:
            return None
        lang, kind, sub_url = picked
        payload = _fetch_bytes(sub_url)
        text = _decode_subtitle_payload(payload, "json")
        if not text.strip():
            return None
        return TranscriptResult(
            title=title,
            language=lang,
            kind=kind,
            text=text.strip(),
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Bilibili dm/view subtitle fallback failed: %s", exc)
        return None


def _decode_subtitle_payload(payload: bytes, ext: str) -> str:
    text = payload.decode("utf-8", errors="replace")
    ext = (ext or "").lower()
    if ext == "json3" or text.lstrip().startswith("{"):
        parsed = parse_json3(text)
        if parsed:
            return parsed
    return parse_vtt_or_srt(text)


def _download_via_ytdlp_files(url: str, lang: str, kind: str) -> Optional[str]:
    """Fallback: ask yt-dlp to write subtitle files under a temp dir."""
    work = Path(tempfile.mkdtemp(prefix="subs_", dir=str(SUBS_DIR)))
    try:
        opts: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "skip_download": True,
            "writesubtitles": kind == "manual",
            "writeautomaticsub": kind == "auto",
            "subtitleslangs": [lang],
            "subtitlesformat": "vtt/srt/best",
            "outtmpl": str(work / "%(id)s"),
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.extract_info(url, download=True)
        candidates = sorted(work.glob("*"))
        for path in candidates:
            if path.suffix.lower() in {".vtt", ".srt", ".ttml", ".srv3", ".json3", ".json"}:
                payload = path.read_bytes()
                return _decode_subtitle_payload(payload, path.suffix.lstrip("."))
        return None
    except Exception as exc:  # noqa: BLE001
        logger.warning("yt-dlp subtitle file fallback failed: %s", exc)
        return None
    finally:
        shutil.rmtree(work, ignore_errors=True)


def fetch_transcript(url: str) -> TranscriptResult:
    """Pull best available captions for the URL and return timed plain text."""
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
            info = ydl.extract_info(url, download=False) or {}
            data = ydl.sanitize_info(info) or {}
    except DownloadError as exc:
        raise ServiceError(f"拉取字幕失败：{exc}", status_code=502) from exc
    except Exception as exc:  # noqa: BLE001
        raise ServiceError("拉取字幕失败，请稍后重试", status_code=502) from exc

    if data.get("_type") == "playlist":
        entries = data.get("entries") or []
        if entries and isinstance(entries[0], dict):
            data = entries[0]

    title = str(data.get("title") or "未命名视频")
    manual = data.get("subtitles") or {}
    automatic = data.get("automatic_captions") or {}
    if not isinstance(manual, dict):
        manual = {}
    if not isinstance(automatic, dict):
        automatic = {}

    # YouTube timedtext CDN is often rate-limited (HTTP 429). Prefer the
    # dedicated transcript API before hammering timedtext / yt-dlp writes.
    if _is_youtube_url(url):
        yt = fetch_youtube_transcript(url, title_hint=title)
        if yt is not None:
            return yt

    picked_kind = "manual"
    picked = _pick_track(manual)
    if picked is None:
        picked_kind = "auto"
        picked = _pick_track(automatic)

    text = ""
    lang = ""
    if picked is not None:
        lang, formats = picked
        entry = _pick_format_entry(formats)
        if entry is not None:
            ext = str(entry.get("ext") or "vtt")
            sub_url = entry.get("url")
            raw_data = entry.get("data")
            if isinstance(raw_data, str) and raw_data.strip():
                text = _decode_subtitle_payload(raw_data.encode("utf-8"), ext)
            elif isinstance(sub_url, str) and urlparse(sub_url).scheme in {"http", "https"}:
                try:
                    payload = _fetch_bytes(sub_url)
                    text = _decode_subtitle_payload(payload, ext)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Direct subtitle URL fetch failed: %s", exc)
                    text = ""
            if not text.strip():
                text = _download_via_ytdlp_files(url, lang, picked_kind) or ""

    if not text.strip():
        bili = fetch_bilibili_transcript(url, title_hint=title)
        if bili is not None:
            return bili

    if not text.strip():
        if picked is None:
            if _is_douyin_url(url):
                raise ServiceError(
                    "该抖音视频没有可导出的字幕文件。页面上看到的字多半是「硬字幕」"
                    "（烧录在画面里），不是可下载的 CC/AI 字幕轨。"
                    "首版无法识别硬字幕，请换有外挂字幕的视频，或等待后续 ASR 能力。",
                    status_code=404,
                )
            raise ServiceError(
                "该视频没有可用字幕（人工或自动）。B 站部分字幕需登录才能经通用通道获取；"
                "若页面可见字幕仍失败，请换一条链接，或等待后续 ASR 能力。",
                status_code=404,
            )
        # Had tracks but all download paths failed (often YouTube timedtext HTTP 429)
        if _is_youtube_url(url):
            raise ServiceError(
                "已检测到 YouTube 字幕轨道，但字幕接口暂时限流或无法读取（常见 HTTP 429）。"
                "请稍等一两分钟再试；若持续失败，可换一条视频。",
                status_code=502,
            )
        raise ServiceError(
            "已找到字幕轨道但无法读取内容，请换一条链接或稍后重试",
            status_code=502,
        )

    return TranscriptResult(
        title=title,
        language=lang,
        kind=picked_kind,
        text=text.strip(),
    )
