# AI 视频总结 — 功能总结（沉淀）

| 项目 | 说明 |
|------|------|
| 产品 | 万能视频下载器 |
| 文档性质 | 已落地功能沉淀（非立项方案） |
| 完成日期 | 2026-11-25（基本功能）；2026-11-26（总结/导图/字幕导出增强） |
| 关联 | [AI视频总结方案设计.md](./AI视频总结方案设计.md)、[方案设计.md](./方案设计.md)、[需求分析.md](./需求分析.md) |
| 状态 | **已完成并人工验收通过**（含 11-26 增强项） |
| 代码提交 | `8851cdb`（已推送 `origin/main`） |

---

## 1. 一句话结论

在下载器内嵌「先读懂再下载」：有字幕的视频可一键生成**流式 Markdown 全文总结**、**章节大纲**、**核心知识点**，并按开闭原则扩展出**思维导图**与**AI 对话**；支持全文总结 Markdown 复制/下载、字幕 TXT/SRT 下载、导图全屏与完整高清 PNG/SVG 导出；无字幕则在总结面板内明确报错，不做 Whisper ASR。

---

## 2. 已交付能力

### 2.1 核心总结

| 能力 | 说明 |
|------|------|
| 入口 | 解析成功后**自动**开始总结；一体工作区左下载 / 右总结；左侧保留「重新总结」（总结进行中禁用） |
| 全文总结 | SSE 流式 Markdown（四段：一句话概括 / 内容要点 / 关键结论 / 适合谁看），前端 `markdown-it` 渲染 |
| 章节大纲 | 与摘要并行生成，带时间戳 + 本章要点 |
| 核心知识点 | 全片提炼要点清单（时间戳 + 一句结论） |
| 字幕原文 | Tab 展示带时间戳文稿；支持下载 TXT / SRT |
| 导出 | 「复制 Markdown」「下载 .md」**仅在全文总结 Tab**；`markdown` 字段仅为全文总结（不含章节/知识点） |
| 错误展示 | 无字幕等失败提示落在总结面板内，不顶到页面上方 |

### 2.2 扩展 Tab（开闭原则）

| Tab | 行为 | 触发时机 |
|-----|------|----------|
| 思维导图 | Markmap 渲染；全屏遮罩；下载完整高清 PNG/SVG；**无**「重新生成」 | 用户首次点开该 Tab |
| AI 对话 | 基于摘要/章节/要点/字幕流式问答 | 总结完成后可提问 |

扩展注册点：`frontend/src/components/summary/extensions.js`  
后端独立路由：`backend/app/api/summary_ext_routes.py`（不改动原有 `/api/summarize*` 契约）。

### 2.3 交互与体验

- 解析结果与 AI 总结同屏一体工作区（桌面左右约 4:6，手机上下堆叠）
- 总结 / 工作区滚动时避开 sticky 顶栏（锚点 `#result-workspace`）
- 导航锚点（`#download` / `#features`）使用 `scroll-padding-top` + `scroll-mt`，避免被顶栏遮挡
- 总结面板 Tab：全文总结 / 章节大纲 / 核心知识点 / 字幕原文 / 思维导图 / AI 对话
- 导图：滚轮平移，Ctrl+滚轮缩放；全屏可用 Esc 退出

---

## 3. 2026-11-26 增强项（本次沉淀重点）

### 3.1 需求与结论

| 需求 | 结论（已确认） |
|------|----------------|
| 丰富全文总结为 Markdown | 固定四段结构；前端渲染；复制/下载只在全文总结 Tab |
| `markdown` 字段语义 | **仅全文总结**（可带 `# 视频标题`），不再拼章节/知识点 |
| 思维导图体验 | 页面内全屏遮罩；可下 PNG/SVG；去掉「重新生成」 |
| 字幕下载 | 同时支持 **TXT**（与展示一致）与 **SRT** |

### 3.2 全文总结（Markdown）

**后端（`summary_service.py`）**

- 流式摘要 Prompt / 一次性 JSON 的 `summary` 均改为输出 Markdown 四段结构
- `build_markdown(title, summary)`：只组装全文总结；正文已有一级标题则不再重复加标题
- 去掉模型偶发的 Markdown 代码围栏

**前端**

- `SummaryPanel.vue`：顶栏不再放复制/下载；按钮移入「全文总结」Tab
- `renderMarkdown.js`（`markdown-it`）+ `style.css` 中 `.summary-md` 样式

### 3.3 字幕下载

- 纯前端 Blob 下载，不新增 API
- `transcriptExport.js`：`[MM:SS]` / `[HH:MM:SS]` 行解析为 SRT（下一段开始时间为本段结束，末段默认 +3s）
- 文件名：`{标题}-字幕.txt` / `{标题}-字幕.srt`

### 3.4 思维导图全屏与导出

**交互（`SummaryMindMapTab.vue`）**

- 全屏：Teleport 遮罩；布局稳定后再 `fit()`，避免 NaN transform
- 去掉「重新生成」；保留首次进入 Tab 懒加载

**导出（`mindmapExport.js`）— 关键决策**

| 问题 | 处理 |
|------|------|
| 导出跟着当前缩放/平移裁切 | 去掉顶层 pan/zoom `transform`，按内容 bbox 设 `viewBox` |
| 缩小后 PNG 发糊 | 按完整内容尺寸高倍率光栅化（约 3–8×，有 canvas 上限保护） |
| PNG canvas 被 foreignObject 污染 | 导出前将 `foreignObject` 转为 SVG `<text>` 再画布渲染 |
| 连接点变实心黑点 | Markmap 折叠圆 `fill=var(--markmap-circle-open-bg)` 在独立 SVG 中变量失效；导出前**烘焙**为白心 + 彩色描边，与网页空心圈一致（**不删除圆点**） |

导出结果与当前视口缩放无关，视觉与页面一比一（含连接空心圈）。

### 3.5 竞品对照（调研摘要）

对齐 BibiGPT / NoteGPT 中「单视频深度学习」刚需：结构化 Markdown 笔记、可带走的字幕、可视化导图导出。未做 Notion/Obsidian 深度集成、批量聚合等广度能力。

---

## 4. 架构（落地态）

```
浏览器 Vue
  │ POST /api/summarize/stream { url }     ← 主路径（SSE）
  │ POST /api/summarize { url }            ← 一次性 JSON（兼容）
  │ POST /api/summarize/mindmap            ← 扩展：导图
  │ POST /api/summarize/chat/stream        ← 扩展：对话 SSE
  ▼
FastAPI
  ├─ subtitle_service.fetch_transcript     字幕（yt-dlp + 站点回退）
  ├─ summary_service.iter_summarize_events Markdown 摘要流式 + 章节并行
  ├─ mindmap_service.generate_mindmap      导图（可 LLM / 结构回退）
  └─ chat_service.iter_chat_events         对话流式
        │
        └─ llm_client / summary 内 LLM 调用
             OpenAI 兼容 Chat Completions（默认 DeepSeek）

前端导出（无后端文件服务）
  ├─ 全文总结 .md / 复制 Markdown
  ├─ 字幕 TXT / SRT
  └─ 导图 PNG / SVG（mindmapExport.js）
```

原则：

1. **字幕与 LLM 解耦**：无字幕直接失败，不混入下载链路  
2. **总结主链路封闭**：扩展走独立服务与 Tab 注册表  
3. **无数据库**：导图/对话上下文由前端携带已总结结果  
4. **导出尽量前端完成**：字幕与导图图片不新增下载接口  

---

## 5. API 一览

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/summarize` | 一次性返回摘要/章节/要点/`markdown`（仅全文总结）/transcript |
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
6. `status: done` → `done`（**仅全文总结**的 markdown）  

### 常见错误

| HTTP / 事件 | 场景 |
|-------------|------|
| 422 | 未配置 `SUMMARY_LLM_API_KEY` |
| 404 | 无可用字幕（含抖音硬字幕等） |
| 502 / SSE `error` | LLM 或字幕拉取失败 |
| 504 | 超时 |

---

## 6. 字幕策略与站点差异

| 站点 | 策略 / 现状 |
|------|-------------|
| 通用 | yt-dlp `subtitles` 优先，其次 `automatic_captions`；语言优先级 zh → en → 其他 |
| B 站 | 匿名场景可能 `need_login_subtitle`；回退 `/x/v2/dm/view` 取 AI/CC 轨，忽略弹幕 |
| YouTube | timedtext 易 429；优先 `youtube-transcript-api`，必要时 `curl_cffi` |
| 抖音 | 多数仅硬字幕，**无法**导出轨；明确 404 提示，留待 ASR |

临时字幕目录：`downloads/subs/`（用完清理）。

---

## 7. 配置

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

## 8. 关键代码地图

### 后端

| 路径 | 职责 |
|------|------|
| `backend/app/services/subtitle_service.py` | 拉取与解析字幕 |
| `backend/app/services/summary_service.py` | Markdown 全文总结（含 SSE）+ `build_markdown` |
| `backend/app/services/llm_client.py` | 扩展用共享 LLM 客户端 |
| `backend/app/services/mindmap_service.py` | 思维导图（含 Markdown 摘要回退清洗） |
| `backend/app/services/chat_service.py` | AI 对话 |
| `backend/app/api/routes.py` | `/summarize`、`/summarize/stream` |
| `backend/app/api/summary_ext_routes.py` | `/summarize/mindmap`、`/summarize/chat/stream` |
| `backend/app/schemas.py` | 请求/响应模型 |

### 前端

| 路径 | 职责 |
|------|------|
| `frontend/src/components/SummaryPanel.vue` | 总结面板、核心 Tab、全文导出按钮、字幕下载 |
| `frontend/src/components/summary/extensions.js` | 扩展 Tab 注册表 |
| `frontend/src/components/summary/SummaryMindMapTab.vue` | 导图、全屏、触发 PNG/SVG 导出 |
| `frontend/src/components/summary/SummaryChatTab.vue` | 对话 |
| `frontend/src/utils/renderMarkdown.js` | 全文总结 Markdown 渲染 |
| `frontend/src/utils/transcriptExport.js` | 字幕 → SRT |
| `frontend/src/utils/mindmapExport.js` | 完整导图 SVG/PNG 导出 |
| `frontend/src/utils/downloadBlob.js` | 通用浏览器下载 |
| `frontend/src/api/client.js` | summarize / stream / mindmap / chat |
| `frontend/src/App.vue` | 流式状态、滚动定位、总结错误入面板 |
| `frontend/src/style.css` | 锚点修正、`.summary-md` 样式 |

依赖补充：`markdown-it`（正文渲染）；导图导出自实现，不依赖后端出图。

---

## 9. 章节大纲 vs 核心知识点 vs 全文总结

| | 全文总结 | 章节大纲 | 核心知识点 |
|--|----------|----------|------------|
| 组织方式 | 固定四段 Markdown | 按时间线切段 | 跨全片提炼 |
| 每条内容 | 概括 / 要点 / 结论 / 受众 | 时间 + 标题 + 本章摘要 | 时间 + 一句结论 |
| 导出 | 复制 / 下载 `.md` | 仅面板展示 | 仅面板展示 |
| 用途 | 读懂整片、带走笔记 | 导航与分段理解 | 速记与复习 |

---

## 10. 验收要点（回归）

1. 配置 Key 后，有字幕的 B 站 / YouTube 可流式出 Markdown 全文总结（含四段标题），并出现章节与要点  
2. 全文总结 Tab 可复制/下载 `.md`，文件**不含**章节大纲与核心知识点；其他 Tab 无这两个按钮  
3. 字幕原文 Tab 可下载 TXT 与 SRT  
4. 思维导图：首次打开生成；可全屏（Esc 退出）；**无**「重新生成」  
5. 导图在放大/缩小/拖移后下载 PNG/SVG，仍为**完整导图**且清晰；连接点为**白心彩色描边空心圈**（与网页一致，非实心黑点）  
6. 无字幕（如多数抖音）→ 总结面板内中文错误，页面顶部不误导  
7. Tab 切换正常；对话可多轮流式回复；滚动不被 sticky 顶栏挡住  
8. `backend/.env` 不被 git 跟踪；仅提交 `.env.example`  

---

## 11. 明确未做 / 后续可做

| 项 | 说明 |
|----|------|
| Whisper / ASR | 硬字幕、无轨视频暂不可总结 |
| 结果缓存 / 历史 | 无持久化，刷新即失 |
| 账号 / VIP 额度 | 未打通 |
| 知识库 / 二次创作 | 未做 |
| 批量总结 | 未做 |
| Notion / Obsidian 同步 | 未做（可用本地下载的 Markdown 手工导入） |

建议后续优先级（可选）：ASR → 本地缓存 → 与 VIP 额度打通。

---

## 12. 与立项方案的差异

立项文档 [AI视频总结方案设计.md](./AI视频总结方案设计.md) 首版曾写「不做思维导图 / AI 追问」，且摘要为短纯文本、`markdown` 含章节与要点整包导出。

落地后：

1. 在**不破坏总结主链路**前提下用扩展模块补齐导图与对话  
2. 全文总结升级为结构化 Markdown；导出收口为「仅全文总结」  
3. 字幕与导图导出能力补齐，满足「带走笔记」场景  

主路径仍为「字幕 → LLM 总结」；导图与对话依赖已有总结结果懒加载/按需调用。
