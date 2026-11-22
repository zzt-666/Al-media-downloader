# 万能视频下载器（AI-media-downloader）

学习向 Web 工具：粘贴链接 → 解析 → 选择清晰度与格式 → 下载到本地。  
解析与下载委托 [yt-dlp](https://github.com/yt-dlp/yt-dlp)，本仓库只做薄封装（FastAPI + Vue）。

> **声明**：仅供学习与个人备份。请尊重版权，禁止将未授权内容用于商用或传播。勿尝试绕过 DRM / 破解会员。

## 功能概览

- 解析公开视频元数据（标题、封面、时长、播放/点赞等，视站点而定）
- 一卡选项：清晰度 + 格式（视频+音频 / 仅视频 / 仅音频）
- 优先兼容播放的 H.264（+ AAC）；抖音等站点做链接规范化与必要兼容处理
- 本机并发下载限制为 1；临时文件约 1 小时清理

## 环境要求

- Python 3.10+（推荐 3.12；可用 `uv` 管理虚拟环境）
- Node.js 18+（npm）
- 系统已安装 **ffmpeg** 并加入 `PATH`（合并音视频 / 部分兼容处理需要）

## 启动后端

```bash
cd backend
# 推荐：
uv venv .venv --python 3.12
uv pip install -r requirements.txt --python .venv/Scripts/python.exe   # Windows
# macOS / Linux 可将路径改为 .venv/bin/python

.venv\Scripts\uvicorn app.main:app --reload --host 127.0.0.1 --port 8000   # Windows
# .venv/bin/uvicorn app.main:app --reload --host 127.0.0.1 --port 8000    # macOS / Linux
```

健康检查：<http://127.0.0.1:8000/api/health>  
期望包含 `ok`、`yt_dlp` 版本、`ffmpeg` 布尔值。

## 启动前端

另开终端：

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 Vite 提示的地址（默认 <http://127.0.0.1:5173>）。  
开发服务器将 `/api` **原样代理**到 `http://127.0.0.1:8000`（不剥离 `/api` 前缀）。

## 使用流程

1. 粘贴 yt-dlp 支持的**单条**公开视频链接，点击解析  
   （抖音请用含 `/video/数字` 或 `modal_id=` 的链接，不要用推荐首页）
2. 在「选择清晰度和格式」中点选一张卡片
3. 点击「下载到本地」，浏览器保存文件

临时文件目录：仓库根下 `downloads/`。

## API 概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/health` | 依赖自检 |
| POST | `/api/parse` | `{ "url" }` → 元数据与 `options` 列表 |
| POST | `/api/download` | `{ "url", "option_id?", "media_type?", "quality?", "format_id?" }` → `{ file_id, filename, size }` |
| GET | `/api/files/{file_id}` | 附件下载 |

## 许可证

本项目采用 [MIT License](./LICENSE)。

## 说明

- 默认 `noplaylist`，避免误下整页播放列表
- 本机学习场景；云上生产部署不在本期范围
- 升级引擎：`uv pip install -U yt-dlp --python backend/.venv/Scripts/python.exe`
