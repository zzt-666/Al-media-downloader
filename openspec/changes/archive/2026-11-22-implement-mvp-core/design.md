# Design

## Context

仓库为绿场：仅有 `docs/需求分析.md`、`docs/方案设计.md` 与 OpenSpec 骨架，无 `backend/` / `frontend/`。行为合同见本 change 的 specs；动机见 `proposal.md`。已确认决策：完整第一版（S1–S4）、同步下载 + `file_id` 二次拉取、前端 **npm**、下载并发 **1**。实现阶段必须用 Context7/官方文档核对 FastAPI、yt-dlp、Vue 3、Vite、Tailwind 最新用法后再写代码（本设计已对照当前文档要点）。

## Goals / Non-Goals

**Goals:**

- 按方案目录落地薄封装：路由不直接堆 yt-dlp options；唯一引擎入口 `ytdlp_service.py`。
- 本机双端口联调可跑通解析→选清晰度→下载→浏览器保存。
- 错误对用户只暴露中文 `detail`；日志可留英文原文。
- 视觉按方案 Token 对齐 painting 风格（非像素级复刻）。

**Non-Goals:**

- 异步任务队列、进度 WebSocket/轮询、直接流式 `POST /api/download` 附件。
- 数据库、登录、支付、真实 AI、Cookie/代理池、Docker/上云。
- Fork 或修改 yt-dlp 源码。

## Decisions

### D1 — 目录与模块边界

采用方案 §3 结构：

- `backend/app/main.py`：应用入口、CORS、路由挂载、启动时清理调度
- `backend/app/api/routes.py`：HTTP 校验与响应
- `backend/app/services/ytdlp_service.py`：唯一 `YoutubeDL` 交互
- `backend/app/services/file_registry.py`（或同目录轻量模块）：内存 `file_id → meta`、TTL 清理、并发信号量
- `backend/app/schemas.py` / `config.py`
- `frontend/`：Vue 3 SFC + Vite + Tailwind；组件按方案 §5.2 拆分

**替代**：单体 `main.py` 全塞 —— 否决，不利于测试与升级引擎。

### D2 — yt-dlp 调用约定（对照官方 Embedding API）

解析：

```python
opts = {"quiet": True, "noplaylist": True, "skip_download": True}
with YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=False)
    data = ydl.sanitize_info(info)
```

下载：

```python
opts = {
    "quiet": True,
    "noplaylist": True,
    "format": format_id or "bv*+ba/b",
    "outtmpl": str(download_dir / "%(id)s_%(format_id)s.%(ext)s"),
    "paths": {"home": str(download_dir)},
}
with YoutubeDL(opts) as ydl:
    info = ydl.extract_info(url, download=True)
    # 真实路径优先 requested_downloads[0]["filepath"]
```

- 对外 JSON 必须先 `sanitize_info` 再裁剪字段。
- 捕获 `yt_dlp.utils.DownloadError`（及超时包装）→ 中文 `detail`。
- 格式过滤：识别 `format_note`/协议中的 storyboard、无 v/a 且极小预览流；排序：有视频轨优先 → 分辨率高→低 → 大小。

**替代**：CLI 子进程 —— 否决，API 更可控且与方案一致。

### D3 — 下载交付：同步 + file_id

1. `POST /api/download` 在线程/同步路由中阻塞至完成（默认超时 **600s**，可配置）。
2. 成功写入 `downloads/`，`uuid4` 登记内存 dict，返回 `{file_id, filename, size}`。
3. `GET /api/files/{file_id}` 使用 FastAPI `FileResponse(path, filename=..., content_disposition_type="attachment")`（官方默认 attachment；非 ASCII 文件名由框架按 RFC 处理）。
4. 全局 `asyncio.Semaphore(1)` 或 `threading.Semaphore(1)`：拿不到锁 → 409/429 + 中文「已有任务进行中」。
5. 后台定时或启动扫描：删除 `created_at` 超过 **1h** 的文件并踢出登记。

**替代**：直接流式响应 / 异步 task_id —— 用户已选 2A，本版不做。

### D4 — API 表面

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | `{ok, yt_dlp, ffmpeg}` |
| POST | `/api/parse` | `{url}` → 元数据 + formats |
| POST | `/api/download` | `{url, format_id?}` → `{file_id, filename, size}` |
| GET | `/api/files/{file_id}` | 附件流 |

URL 仅允许 `http`/`https`。CORS 开发期允许 `http://127.0.0.1:5173` 与 `http://localhost:5173`（FastAPI `CORSMiddleware`）。

### D5 — 前端栈与联调

- `npm create vite@latest` Vue 模板脚手架到 `frontend/`（或等价手写），包管理 **npm**。
- Vue 3 `<script setup>` + Composition API（`ref` 管理 url/loading/error/result）。
- Tailwind 自定义主色 `#1777FF` 等方案 Token。
- **Vite proxy（关键）**：后端路由本身带 `/api` 前缀，代理 **不得** `rewrite` 去掉 `/api`：

```js
server: {
  proxy: {
    '/api': {
      target: 'http://127.0.0.1:8000',
      changeOrigin: true,
    },
  },
}
```

- 下载成功后：`window.location` / 隐藏 `<a download>` / `fetch`+blob 任一稳定方式触发保存；优先 `GET /api/files/{file_id}` 导航或 blob，确保手机浏览器也能下。
- 第一版不引入 Vue Router；锚点分区即可。
- HTTP 客户端用原生 `fetch`，少依赖。

**替代**：pnpm / axios / 直接流式下载 —— 与已确认决策不符。

### D6 — ffmpeg 探测

`health` 用 `shutil.which("ffmpeg")`（或 yt-dlp 内部探测若文档推荐且稳定）返回布尔。合并失败时错误文案引导安装 ffmpeg。

### D7 — 文档与自测门槛

根 `README.md` 写清 Python venv、`uvicorn`、`npm run dev`、ffmpeg、健康检查。实现完成后按方案 §9.1 + §9.2 自测；**仅 API 不算完成**。E2E 用有权访问的公开学习向链接（不固化 URL）。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 同步下载长时间占用 worker | 本机学习可接受；超时 10 分钟；并发 1；后续可升异步 |
| 站点反爬 / 引擎失效 | 升级 yt-dlp；UI 提示更新引擎 |
| 无 ffmpeg 导致合并失败 | health 暴露；错误中文引导；README 安装说明 |
| 磁盘占满 | `downloads/` 隔离 + 1h TTL + 并发 1 |
| Vite 误配 rewrite 导致 404 | 明确不 strip `/api`；联调时先打 health |
| 中文文件名 Content-Disposition | 使用 `FileResponse(filename=...)`，依赖框架 UTF-8 编码 |

## Migration Plan

绿场首次落地，无旧数据迁移。回滚即删除新增目录/依赖或回退 git。进程重启清空内存 `file_id` 登记（可接受）；磁盘残留由 TTL/启动清理处理。

## Open Questions

无阻塞实现的未决项。以下实现时可微调且不改 specs：

- 格式列表是否额外提供「最佳（自动合并）」伪选项 vs 仅空 `format_id` 走默认 —— 建议 UI 增加「最佳」选项，请求时不传或传空 `format_id`。
- 精确 HTTP 状态码（400 vs 502）在友好 `detail` 前提下可按 FastAPI/HTTPException 惯例微调。
