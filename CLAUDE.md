# CLAUDE.md

<!--
維護原則：
- 只寫 Claude 從程式碼看不出來的事，控制在 200 行內
- @path 引用每次 session 都會載入；非必要的文件寫成「需要時讀 docs/xxx.md」
- 規則改了就改這份檔案（進 git review），不要只在對話中口頭交代
-->

## 專案概述
<專案名稱>：<一句話描述用途與使用者>。

## 技術棧
Python 3.12 + FastAPI + SQLAlchemy 2.0 (async) + PostgreSQL 16 + Alembic，套件管理使用 uv。

## 常用指令
- 安裝依賴：`uv sync`
- 啟動開發伺服器：`uv run fastapi dev app/main.py`
- 啟動本地 DB：`docker compose up -d db`
- 測試：`uv run pytest -x -q`（單一檔案：`uv run pytest tests/path/test_x.py -q`）
- Lint / 格式化：`uv run ruff check --fix . && uv run ruff format .`
- 型別檢查：`uv run mypy app`
- 產生 migration：`uv run alembic revision --autogenerate -m "<描述>"`
- 套用 migration：`uv run alembic upgrade head`

## 目錄結構
- `app/main.py`：FastAPI 進入點、router 註冊
- `app/api/`：路由層（只做參數驗證與呼叫 service，不寫商業邏輯）
- `app/services/`：商業邏輯
- `app/repositories/`：DB 存取（SQLAlchemy 查詢只能出現在這裡）
- `app/models/`：SQLAlchemy ORM models
- `app/schemas/`：Pydantic request/response schemas
- `app/core/`：設定（pydantic-settings）、DB session、例外處理、安全性
- `alembic/`：migrations
- `tests/`：結構對應 `app/`

## 程式碼慣例
- SQLAlchemy 2.0 async 寫法（`select()` + `AsyncSession`），不使用 `session.query()`
- Pydantic v2（`model_config`、`model_validate`），不使用 v1 的 `Config` / `parse_obj`
- 依賴注入一律用 `Depends`；DB session 從 `app/core/db.py:get_session` 取得
- ORM model 不可直接回傳，必須轉成 `schemas/` 的 response model
- 所有函式加型別註記
- 錯誤用自訂例外 + `app/core/exceptions.py` 的 handler，不在 router 寫 try/except
- 設定值從環境變數讀取（`app/core/config.py`），不可寫死

## 資料庫規則
- 修改 model 後必須產生 migration，並人工檢查 autogenerate 結果
- 不要修改已存在的 migration 檔，只能新增
- 金額用 `Numeric`；時間一律 `TIMESTAMP WITH TIME ZONE`（UTC）

## 測試
- 新功能或修 bug 必須附測試；使用獨立 test DB（見 `tests/conftest.py`）
- API 測試使用 `httpx.AsyncClient` + `pytest-asyncio`

## 文件位置（需要時再讀，不要一開始全部讀取）
- 架構說明：`docs/architecture.md`
- 進度與待辦：`docs/progress.md`
- 功能規格：`docs/specs/`
- 架構決策紀錄（ADR）：`docs/decisions/`
- PR review 規則（/review 與 GitHub review 共用）：`REVIEW.md`

## Git 流程
- 分支命名：`feat/<主題>`、`fix/<主題>`、`chore/<主題>`
- 不可直接 push 到 main / master，一律透過 PR
- Commit 訊息遵循 Conventional Commits（`feat: ...`、`fix: ...`、`refactor: ...`）

## 禁止事項
- 不要讀取或修改 `.env`、金鑰、憑證等機密檔案
- 不要新增或升級依賴套件，除非先詢問我
- 不要手動編輯 lockfile
- 不要加多餘註解，不要新增未被要求的功能
- 不確定需求時先提問，不要自行假設
- 不可猜測 API、設定或參數；查不到就列出待確認事項
- 沒有實際執行過的測試，不可回報為通過

## 工作方式
- 較大的改動先用 Plan mode 提出計畫，我確認後再實作
- 一次只做一個可驗收的功能；改了規格、測試流程或架構，要同步更新 `docs/`
- 完成任務前，必須執行本檔「常用指令」中的測試與 lint，並確認全部通過
- 長任務：開始時讀 `docs/progress.md`，告一段落時用 `/progress` 更新
- 大範圍搜尋程式碼交給 researcher subagent，只回報結論
- 回覆使用繁體中文；程式碼、識別名稱、commit 訊息使用英文
