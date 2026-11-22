# Proposal

## Why

日常需要把公开视频保存到本机，但官方入口受限、工具碎片化。本仓库已确认需求与方案，却尚无前后端代码；现在需要按文档交付第一版「解析 → 选清晰度 → 下载」主链路，并带上可转化 UI 与合规声明，便于本机学习与后续验收。

## What Changes

- 从零搭建 **FastAPI** 后端：薄封装 **yt-dlp**，提供健康检查、解析、同步下载、按 `file_id` 取文件。
- 从零搭建 **Vue 3 + Vite + Tailwind** 前端（**npm**）：painting 风格单页，完成粘贴解析、选格式、下载全流程；含平台 Pill、进阶能力占位、页脚合规声明与移动端布局。
- 本机运行说明（根 README）：Python/Node/ffmpeg、双端口联调、Vite 代理 `/api`。
- 临时文件目录 `downloads/`、内存任务登记、**并发上限 1**、TTL 清理；默认 `noplaylist`。
- **不做**：真实支付/登录/AI、数据库、异步进度轮询、Cookie 登录下载、阿里云部署、改 yt-dlp 源码。

## Capabilities

### New Capabilities

- `video-parse`: 校验 http(s) URL，经 yt-dlp 解析并返回精简元数据与可选格式列表；解析失败返回可读中文错误。
- `video-download`: 按选定或默认格式同步下载到隔离目录，登记 `file_id` 后二次拉取附件；含并发限制、超时、TTL 清理与友好错误映射。
- `runtime-health`: 暴露依赖自检（服务可用、yt-dlp 版本、ffmpeg 是否可用）。
- `product-web-ui`: 产品单页 UI 与前后端联调行为（Hero、结果区、平台展示、占位模块、合规页脚、加载/错误态、响应式）。

### Modified Capabilities

- （无；仓库尚无主规格）

## Impact

- 新增目录：`backend/`、`frontend/`、`downloads/`（gitignore）、根 `README.md`。
- 依赖：Python（fastapi、uvicorn、yt-dlp、pydantic）、系统 ffmpeg、Node LTS + npm（Vue/Vite/Tailwind）。
- 开发期 CORS + Vite 代理联调 `5173` ↔ `8000`。
- 验收以文档 §8 / 方案 §9 为准：接口自测 + 浏览器点击 E2E（不可仅测 API）。
