# AI 视频总结 — 功能总结（沉淀）

| 项目 | 说明 |
|------|------|
| 产品 | 万能视频下载器 |
| 文档性质 | 已落地功能沉淀（非立项方案） |
| 完成日期 | 2026-11-25（基本功能）；2026-11-26（总结/导图/字幕导出增强） |
| 关联 | [AI视频总结方案设计.md](./AI视频总结方案设计.md)、[方案设计.md](./方案设计.md)、[需求分析.md](./需求分析.md) |
| 状态 | **基本功能已验收；增强项待本次人工验收** |

---

## 1. 一句话结论

在下载器内嵌「先读懂再下载」：有字幕的视频可一键生成**流式 Markdown 全文总结**、**章节大纲**、**核心知识点**，并按开闭原则扩展出**思维导图**与**AI 对话**；无字幕则在总结面板内明确报错，不做 Whisper ASR。

---

## 2. 已交付能力

### 2.1 核心总结

| 能力 | 说明 |
|------|------|
| 入口 | 解析结果区「AI 总结」按钮（与下载并列） |
| 全文总结 | SSE 流式 Markdown（四段：一句话概括 / 内容要点 / 关键结论 / 适合谁看），前端渲染 |
| 章节大纲 | 与摘要并行生成，带时间戳 + 本章要点 |
| 核心知识点 | 全片提炼要点清单（时间戳 + 一句结论） |
| 字幕原文 | Tab 展示带时间戳文稿；支持下载 TXT / SRT |
| 导出 | 「复制 Markdown」「下载 .md」仅在全文总结 Tab；内容仅为全文总结 |
| 错误展示 | 无字幕等失败提示落在总结面板内，不顶到页面上方 |

### 2.2 扩展 Tab（开闭原则）

| Tab | 行为 | 触发时机 |
|-----|------|----------|
| 思维导图 | Markmap 渲染；支持全屏、下载 PNG/SVG（无重新生成） | 用户首次点开该 Tab |
| AI 对话 | 基于摘要/章节/要点/字幕流式问答 | 总结完成后可提问 |

扩展注册点：`frontend/src/components/summary/extensions.js`  
后端独立路由：`backend/app/api/summary_ext_routes.py`（不改动原有 `/api/summarize*` 契约）。

### 2.3 交互与体验

- 总结 / 解析结果卡片滚动时避开 sticky 顶栏
- 导航锚点（`#download` / `#features`）使用 `scroll-padding-top` + `scroll-mt`，避免被顶栏遮挡
- 总结面板 Tab：全文总结 / 章节大纲 / 核心知识点 / 字幕原文 / 思维导图 / AI 对话

---

## 3. 架构（落地态）

```
浏览器 Vue
  │ POST /api/summarize/stream { url }     ← 主路径（SSE）
  │ POST /api/summarize { url }            ← 一次性 JSON（兼容）
  │ POST /api/summarize/mindmap            ← 扩展：导图
  │ POST /api/summarize/chat/stream        ← 扩展：对话 SSE
  ▼
FastAPI
  ├─ subtitle_service.fetch_transcript     字幕（yt-dlp + 站点回退）
  ├─ summary_service.iter_summarize_events 摘要流式 + 章节并行
  ├─ mindmap_service.generate_mindmap      导图（可 LLM / 结构回退）
  └─ chat_service.iter_chat_events         对话流式
        │
        └─ llm_client / summary 内 LLM 调用
             OpenAI 兼容 Chat Completions（默认 DeepSeek）
```

原则：

1. **字幕与 LLM 解耦**：无字幕直接失败，不混入下载链路  
2. **总结主链路封闭**：扩展走独立服务与 Tab 注册表  
3. **无数据库**：导图/对话上下文由前端携带已总结结果  

---

## 4. API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/summarize` | 一次性返回摘要/章节/要点/markdown/transcript |
| POST | `/api/summarize/stream` | SSE：`status` / `meta` / `summary_delta` / `summary` / `chapters` / `key_points` / `done` / `error` |
| POST | `/api/summarize/mindmap` | 入参为已有总结字段 → `{ markdown, source: llm\|fallback }` |
| POST | `/api/summarize/chat/stream` | SSE：`status` / `delta` / `done` / `error` |
| GET | `/api/health` | 含 `llm_configured` |

### 流式总结事件顺序（典型）

1. `status: fetching_subtitles`  
2. `meta`（标题、语言、字幕类型、transcript）  
3. `status: generating`  
4. 多次 `summary_delta`（并行后台拉章节/要点）  
5. `summary` → `chapters` → `key_points`  
6. `status: done` → `done`（完整 markdown）  

### 常见错误

| HTTP / 事件 | 场景 |
|-------------|------|
| 422 | 未配置 `SUMMARY_LLM_API_KEY` |
| 404 | 无可用字幕（含抖音硬字幕等） |
| 502 / SSE `error` | LLM 或字幕拉取失败 |
| 504 | 超时 |

---

## 5. 字幕策略与站点差异

| 站点 | 策略 / 现状 |
|------|-------------|
| 通用 | yt-dlp `subtitles` 优先，其次 `automatic_captions`；语言优先级 zh → en → 其他 |
| B 站 | 匿名场景可能 `need_login_subtitle`；回退 `/x/v2/dm/view` 取 AI/CC 轨，忽略弹幕 |
| YouTube | timedtext 易 429；优先 `youtube-transcript-api`，必要时 `curl_cffi` |
| 抖音 | 多数仅硬字幕，**无法**导出轨；明确 404 提示，留待 ASR |

临时字幕目录：`downloads/subs/`（用完清理）。

---

## 6. 配置

文件：`backend/.env`（**已 gitignore，勿提交**）；模板：`backend/.env.example`。

| 变量 | 默认 | 说明 |
|------|------|------|
| `SUMMARY_LLM_API_KEY` | 空 | 必填才可用总结/导图/对话 |
| `SUMMARY_LLM_BASE_URL` | `https://api.deepseek.com/v1` | OpenAI 兼容 Base |
| `SUMMARY_LLM_MODEL` | `deepseek-chat` | 模型名 |
| `SUMMARY_TIMEOUT_SECONDS` | `120` | HTTP 超时 |
| `SUMMARY_MAX_TRANSCRIPT_CHARS` | `60000` | 送入模型的字幕上限 |

修改 Key 后需**重启后端**。未配置时解析/下载仍可用。

---

## 7. 关键代码地图

### 后端

| 路径 | 职责 |
|------|------|
| `backend/app/services/subtitle_service.py` | 拉取与解析字幕 |
| `backend/app/services/summary_service.py` | 总结（含 SSE 事件流） |
| `backend/app/services/llm_client.py` | 扩展用共享 LLM 客户端 |
| `backend/app/services/mindmap_service.py` | 思维导图 |
| `backend/app/services/chat_service.py` | AI 对话 |
| `backend/app/api/routes.py` | `/summarize`、`/summarize/stream` |
| `backend/app/api/summary_ext_routes.py` | `/summarize/mindmap`、`/summarize/chat/stream` |
| `backend/app/schemas.py` | 请求/响应模型 |

### 前端

| 路径 | 职责 |
|------|------|
| `frontend/src/components/SummaryPanel.vue` | 总结面板与核心 Tab |
| `frontend/src/components/summary/extensions.js` | 扩展 Tab 注册表 |
| `frontend/src/components/summary/SummaryMindMapTab.vue` | 导图（Markmap） |
| `frontend/src/components/summary/SummaryChatTab.vue` | 对话 |
| `frontend/src/api/client.js` | summarize / stream / mindmap / chat |
| `frontend/src/App.vue` | 流式状态、滚动定位、总结错误入面板 |
| `frontend/src/style.css` | `scroll-padding-top` 等全局锚点修正 |

---

## 8. 章节大纲 vs 核心知识点

| | 章节大纲 | 核心知识点 |
|--|----------|------------|
| 组织方式 | 按时间线切段 | 跨全片提炼 |
| 每条内容 | 时间 + 标题 + 本章摘要 | 时间 + 一句结论 |
| 用途 | 导航与分段理解 | 速记与复习 |

---

## 9. 验收要点（回归）

1. 配置 Key 后，有字幕的 B 站 / YouTube 可流式出 Markdown 全文总结（含四段标题），并出现章节与要点  
2. 全文总结 Tab 可复制/下载 `.md`，文件**不含**章节大纲与核心知识点；其他 Tab 无这两个按钮  
3. 字幕原文 Tab 可下载 TXT 与 SRT  
4. 思维导图：首次打开生成；可全屏（Esc 退出）；可下载 PNG/SVG；无「重新生成」  
5. 无字幕（如多数抖音）→ 总结面板内中文错误，页面顶部不误导  
6. Tab 切换正常；对话可多轮流式回复；滚动不被 sticky 顶栏挡住  
7. `backend/.env` 不被 git 跟踪；仅提交 `.env.example`  

---

## 10. 明确未做 / 后续可做

| 项 | 说明 |
|----|------|
| Whisper / ASR | 硬字幕、无轨视频暂不可总结 |
| 结果缓存 / 历史 | 无持久化，刷新即失 |
| 账号 / VIP 额度 | 未打通 |
| 知识库 / 二次创作 | 未做 |
| 批量总结 | 未做 |

建议后续优先级（可选）：ASR → 本地缓存 → 与 VIP 额度打通。

---

## 11. 与立项方案的差异

立项文档 [AI视频总结方案设计.md](./AI视频总结方案设计.md) 首版曾写「不做思维导图 / AI 追问」。落地后在**不破坏总结主链路**前提下已用扩展模块补齐二者；主路径仍为「字幕 → LLM 结构化总结」，导图与对话依赖已有总结结果懒加载/按需调用。
