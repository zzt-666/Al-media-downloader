"""Mind-map generation from an already-produced summary (extension module)."""

from __future__ import annotations

import logging
import re

from app.schemas import MindmapRequest, MindmapResponse, SummaryChapter, SummaryKeyPoint
from app.services import llm_client
from app.services.ytdlp_service import ServiceError

logger = logging.getLogger(__name__)

_SYSTEM = """你是学习笔记助手。根据视频总结材料，输出一份 Markdown 思维导图大纲（不要代码围栏）。
格式要求：
1. 第一行用一级标题 # 作为中心主题（简短）；
2. 用 ## / ### / - 表示层级，最多 4 层；
3. 节点文字简洁，便于导图阅读；
4. 只依据给定材料，不编造；
5. 全文简体中文。"""


def build_fallback_markdown(
    title: str,
    summary: str,
    chapters: list[SummaryChapter],
    key_points: list[SummaryKeyPoint],
) -> str:
    root = (title or "视频总结").strip() or "视频总结"
    lines = [f"# {root}", ""]
    if summary.strip():
        lines.append("## 整体摘要")
        # Strip markdown markers so fallback bullets stay readable
        plain = re.sub(r"^#{1,6}\s*", "", summary.strip(), flags=re.M)
        plain = re.sub(r"[*`_#>]+", "", plain)
        parts = re.split(r"[。！？\n]+", plain)
        bullets = [p.strip(" -") for p in parts if p.strip(" -")][:8]
        if bullets:
            for b in bullets:
                lines.append(f"- {b[:120]}")
        else:
            lines.append(f"- {plain[:120]}")
        lines.append("")
    if chapters:
        lines.append("## 章节结构")
        for ch in chapters:
            label = f"[{ch.start}] {ch.title}".strip()
            lines.append(f"### {label}")
            if ch.summary.strip():
                for piece in re.split(r"[。！？\n]+", ch.summary.strip()):
                    piece = piece.strip()
                    if piece:
                        lines.append(f"- {piece}")
            lines.append("")
    if key_points:
        lines.append("## 核心知识点")
        for kp in key_points:
            text = kp.text.strip()
            if not text:
                continue
            ts = kp.timestamp.strip()
            lines.append(f"- {f'[{ts}] ' if ts and ts != '—' else ''}{text}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _sanitize_markdown(md: str, fallback_title: str) -> str:
    text = (md or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:markdown|md)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    if not text:
        return f"# {fallback_title or '视频总结'}\n"
    if not text.lstrip().startswith("#"):
        text = f"# {fallback_title or '视频总结'}\n\n{text}"
    return text + ("\n" if not text.endswith("\n") else "")


def generate_mindmap(body: MindmapRequest) -> MindmapResponse:
    llm_client.require_llm_key()
    chapters = body.chapters or []
    key_points = body.key_points or []
    fallback = build_fallback_markdown(body.title, body.summary, chapters, key_points)

    if not body.summary.strip() and not chapters and not key_points:
        raise ServiceError("请先完成视频总结后再生成思维导图", status_code=400)

    chapter_lines = "\n".join(
        f"- [{c.start}] {c.title}: {c.summary}" for c in chapters
    ) or "（无）"
    point_lines = "\n".join(
        f"- [{k.timestamp}] {k.text}" for k in key_points
    ) or "（无）"
    user = (
        f"视频标题：{body.title}\n\n"
        f"整体摘要：\n{body.summary or '（无）'}\n\n"
        f"章节大纲：\n{chapter_lines}\n\n"
        f"核心知识点：\n{point_lines}\n\n"
        "请输出 Markdown 思维导图大纲。"
    )

    source = "fallback"
    markdown = fallback
    try:
        raw = llm_client.post_chat(
            [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": user},
            ],
            temperature=0.3,
        )
        markdown = _sanitize_markdown(raw, body.title)
        source = "llm"
    except ServiceError:
        logger.warning("Mindmap LLM failed; using structural fallback")
        markdown = fallback
        source = "fallback"

    return MindmapResponse(markdown=markdown, source=source)  # type: ignore[arg-type]
