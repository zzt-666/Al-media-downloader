from typing import Literal, Optional

from pydantic import BaseModel, Field

MediaType = Literal["av", "video", "audio"]


class ParseRequest(BaseModel):
    url: str = Field(..., description="Video page URL")


class DownloadOption(BaseModel):
    """One clickable card: clarity + format already combined."""

    id: str  # e.g. "av:1080", "video:720", "audio:best"
    label: str  # e.g. "1080P 最佳（视频+音频）"
    sublabel: str  # e.g. "MP4 · 含音频"
    media_type: MediaType
    quality: str
    # Concrete yt-dlp format_id when known (avoids wrong height/size picks)
    format_id: Optional[str] = None
    filesize: Optional[int] = None
    recommended: bool = False


class ParseResponse(BaseModel):
    id: str
    title: str
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    uploader: Optional[str] = None
    webpage_url: Optional[str] = None
    extractor: Optional[str] = None
    extractor_key: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    upload_date: Optional[str] = None  # YYYY-MM-DD when available
    description: Optional[str] = None
    # Soft hint e.g. image-note with music only (not a hard error)
    notice: Optional[str] = None
    options: list[DownloadOption]


class DownloadRequest(BaseModel):
    url: str
    media_type: MediaType = "av"
    quality: Optional[str] = "best"
    format_id: Optional[str] = None
    # Prefer sending option_id from parse; backend also accepts media_type+quality
    option_id: Optional[str] = None


class DownloadResponse(BaseModel):
    file_id: str
    filename: str
    size: int


class HealthResponse(BaseModel):
    ok: bool
    yt_dlp: Optional[str] = None
    ffmpeg: bool
    llm_configured: bool = False


class SummarizeRequest(BaseModel):
    url: str = Field(..., description="Video page URL")


class SummaryChapter(BaseModel):
    start: str
    title: str
    summary: str = ""


class SummaryKeyPoint(BaseModel):
    timestamp: str
    text: str


class SummarizeResponse(BaseModel):
    title: str
    source_lang: Optional[str] = None
    subtitle_kind: Literal["manual", "auto"]
    summary: str
    chapters: list[SummaryChapter]
    key_points: list[SummaryKeyPoint]
    markdown: str
    transcript: Optional[str] = None


# --- Summary extensions (mindmap / chat); do not alter SummarizeResponse contract ---


class MindmapRequest(BaseModel):
    title: str = ""
    summary: str = ""
    chapters: list[SummaryChapter] = []
    key_points: list[SummaryKeyPoint] = []


class MindmapResponse(BaseModel):
    markdown: str
    source: Literal["llm", "fallback"] = "llm"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatStreamRequest(BaseModel):
    title: str = ""
    summary: str = ""
    transcript: Optional[str] = None
    chapters: list[SummaryChapter] = []
    key_points: list[SummaryKeyPoint] = []
    messages: list[ChatMessage]
