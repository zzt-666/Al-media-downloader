# AI 视频总结 — 方案设计

| 项目 | 说明 |
|------|------|
| 产品名称 | 万能视频下载器 |
| 文档版本 | v1.0 |
| 创建日期 | 2026-11-25 |
| 状态 | 已确认，开发中 |
| 关联 | [需求分析.md](./需求分析.md)、[方案设计.md](./方案设计.md)、竞品调研（BibiGPT / NoteGPT） |

---

## 1. 已确认范围（首版）

来自竞品调研结论 §5，本机学习场景默认如下：

| 项 | 结论 |
|----|------|
| 入口 | 解析成功后，在结果区提供「AI 总结」按钮（与下载并列） |
| 输出 | 整体摘要 + 带时间戳章节大纲 + 核心知识点；支持复制 / 导出 Markdown |
| 文本来源 | **仅** yt-dlp 拉取人工字幕或自动字幕；无字幕则明确报错（首版不做 Whisper/ASR） |
| LLM | 本机配置 OpenAI 兼容 API（环境变量）；推荐 DeepSeek |
| 不做 | 思维导图、AI 追问、知识库、二次创作、批量、账号支付 |

差异化叙事：下载器内嵌「快速读懂」，先总结再决定是否下载原片。

---

## 2. 架构

```
浏览器 Vue
  │ POST /api/summarize { url }
  ▼
FastAPI routes
  │
  ├─ ytdlp_service.validate_url
  ├─ subtitle_service.fetch_transcript  ← yt-dlp 字幕/自动字幕
  └─ summary_service.summarize          ← OpenAI 兼容 Chat Completions
        │
        ▼
  SummaryResponse（摘要 / 章节 / 要点 / markdown）
```

原则：字幕与 LLM 各自独立模块；路由层不直接拼 prompt；仍无数据库。

---

## 3. API

### `POST /api/summarize`

请求：

```json
{ "url": "https://..." }
```

成功响应：

```json
{
  "title": "视频标题",
  "source_lang": "zh-Hans",
  "subtitle_kind": "manual|auto",
  "summary": "一段整体摘要…",
  "chapters": [
    { "start": "00:00", "title": "开场", "summary": "…" }
  ],
  "key_points": [
    { "timestamp": "01:21", "text": "要点…" }
  ],
  "markdown": "# …完整可导出 Markdown…"
}
```

错误（`detail` 中文）：

| HTTP | 场景 |
|------|------|
| 400 | URL 无效 / 非单视频 |
| 422 | 未配置 `SUMMARY_LLM_API_KEY` |
| 404 | 该视频无可用字幕（人工/自动均无） |
| 502 | 字幕拉取失败或 LLM 调用失败 |
| 504 | 超时 |

### `GET /api/health` 扩展

增加 `llm_configured: bool`（仅表示是否配置了 API Key，不探测远端连通性）。

---

## 4. 字幕策略

1. `validate_url` 规范化链接（复用现有抖音/分享文案逻辑）。
2. `extract_info(..., download=False)` 读取 `subtitles` 与 `automatic_captions`。
3. 语言优先级：`zh-Hans` → `zh-CN` → `zh*` → `en*` → 其余第一个可用。
4. 优先人工字幕，其次自动字幕。
5. 下载所选字幕 URL（vtt/srt/json3 等），解析为带时间戳的纯文本行，例如 `[01:21] …`。
6. 过长文稿按字符上限截断（保留前后文提示），避免撑爆上下文。

临时字幕文件若落盘，放在 `downloads/subs/`，用完即删。

**B 站特例：** `/x/player/v2` 与 `/x/player/wbi/v2` 常带 `need_login_subtitle=true`，未登录时字幕列表为空（页面上仍可能显示 AI/CC 字幕）。首版增加匿名回退：`/x/web-interface/view` 取 aid/cid → `/x/v2/dm/view` 取字幕轨 → 下载 JSON 正文。忽略 `danmaku` 弹幕轨。

**YouTube 特例：** yt-dlp 常能列出 `automatic_captions`，但 timedtext CDN 易返回 HTTP 429。优先用 `youtube-transcript-api` 拉取文稿。

**抖音限制：** 多数视频只有「硬字幕」（烧录在画面），API/yt-dlp 无外挂字幕轨；首版无法总结，需后续 ASR。

---

## 5. LLM 策略

环境变量：

| 变量 | 默认 | 说明 |
|------|------|------|
| `SUMMARY_LLM_API_KEY` | （空） | 必填才可总结；写在 `backend/.env` |
| `SUMMARY_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容 base |
| `SUMMARY_LLM_MODEL` | `deepseek-chat` | 模型名 |
| `SUMMARY_TIMEOUT_SECONDS` | `120` | HTTP 超时 |
| `SUMMARY_MAX_TRANSCRIPT_CHARS` | `60000` | 送入模型的字幕上限 |

调用：`POST {BASE}/chat/completions`，要求模型返回 JSON；服务端校验并生成 `markdown` 字段。

---

## 6. 前端

- [`ParseResult.vue`](../frontend/src/components/ParseResult.vue)：增加「AI 总结」按钮。
- 新建 `SummaryPanel.vue`：展示摘要 / 章节 / 要点；「复制 Markdown」「下载 .md」。
- [`client.js`](../frontend/src/api/client.js)：`summarizeVideo(url)`。
- [`FeaturePlaceholders.vue`](../frontend/src/components/FeaturePlaceholders.vue)：AI 总结卡片改为「解析后可用」，字幕翻译仍占位。

---

## 7. 自测清单

1. 未配置 Key → 422，前端可读提示。
2. 有字幕的 B 站/YouTube 公开视频 → 返回摘要+章节+要点+markdown。
3. 确认无字幕的链接 → 404 中文说明。
4. health 中 `llm_configured` 与是否设置 Key 一致。
5. 手机宽度下结果区可滚动阅读、可复制。

---

## 8. 后续（非本版）

- 无字幕时本机 Whisper ASR
- 思维导图 / AI 追问
- 总结结果缓存与历史
- 与 VIP 额度打通
