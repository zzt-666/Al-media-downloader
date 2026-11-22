# Tasks

## 1. Backend scaffold and health

- [x] 1.1 Create `backend/app` package layout (`main.py`, `api/routes.py`, `services/`, `schemas.py`, `config.py`), `requirements.txt` (fastapi, uvicorn, yt-dlp, pydantic), and `downloads/` + root `.gitignore` entries; verify package imports with `python -c "from app.main import app"` from `backend/` after venv install
- [x] 1.2 Before coding routes/services, confirm latest FastAPI `CORSMiddleware` / `FileResponse` and yt-dlp `YoutubeDL.extract_info` / `sanitize_info` usage via Context7 or official docs; note any API drift in a short comment or README caveat if needed
- [x] 1.3 Implement `config.py` (DOWNLOAD_DIR, concurrency=1, TTL=1h, download timeout=600s, allowed URL schemes) and `GET /api/health` returning `{ok, yt_dlp, ffmpeg}`; verify with a request that returns yt-dlp version and ffmpeg boolean

## 2. Parse and download services

- [x] 2.1 Implement URL validation (http/https only) and `ytdlp_service.parse` with `noplaylist`/`skip_download`, `sanitize_info`, field trim, format filter/sort; verify `POST /api/parse` returns title+formats for a public supported URL and Chinese errors for empty/`file://`/garbage URLs
- [x] 2.2 Implement file registry + semaphore(1) + TTL cleanup and `ytdlp_service.download` (format_id or default `bv*+ba/b`, path from `requested_downloads` when present); verify `POST /api/download` returns `file_id`/`filename`/`size` and a second concurrent download is rejected with Chinese busy detail
- [x] 2.3 Implement `GET /api/files/{file_id}` via `FileResponse` attachment and 404 for missing/expired ids; verify file downloads and plays locally, and expired/unknown id returns Chinese not-found detail
- [x] 2.4 Wire CORS for Vite origins, map `DownloadError`/timeout/missing-ffmpeg to Chinese `detail` (no stack to client); verify failed parse/download responses are JSON with Chinese detail only

## 3. Frontend product UI

- [x] 3.1 Scaffold `frontend/` with Vue 3 + Vite + Tailwind via **npm**, configure proxy `/api` → `http://127.0.0.1:8000` **without** stripping `/api`; verify `npm run dev` loads and `GET /api/health` through the proxy succeeds
- [x] 3.2 Before UI wiring, confirm Vue 3 `<script setup>` and Vite proxy patterns via Context7/official docs; implement `src/api` fetch helpers for parse/download/files
- [x] 3.3 Build AppHeader + HeroSearch + ParseResult (loading/error/success, format list or cards,「最佳」选项传空 format_id, download loading + file save); verify browser flow: paste → parse → select → download saves a file
- [x] 3.4 Add PlatformPills, FeaturePlaceholders（即将上线）, AppFooter 合规文案, apply design tokens (`#1777FF` etc.) and phone-width layout; verify placeholders/footer visible and narrow viewport still completes parse controls

## 4. Docs and autonomous verification

- [x] 4.1 Write root `README.md` (Python venv, uvicorn :8000, npm frontend, ffmpeg, health check, learning/copyright note); verify a clean machine can follow it to start both servers
- [x] 4.2 Run API self-tests T1–T5 from 方案设计 §9.1 (health, parse, download+file, illegal URL, unsupported/unavailable); verify all pass with Chinese errors where expected
- [x] 4.3 Run browser click E2E-1～E2E-6 from 方案设计 §9.2 (page open, parse success, download, parse fail UI, mobile width, placeholders+compliance); verify each case and record brief results/screenshots before requesting human acceptance

## Workflow follow-up

- After human acceptance, archive this change with the openspec-archive-change workflow when requested.
- Do not start implementation until the user explicitly asks to apply this change.
