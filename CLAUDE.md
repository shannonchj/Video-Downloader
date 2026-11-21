# CLAUDE.md

## 專案概述
MediaBot：擁有者個人使用的自架工具。透過 Telegram Bot 傳送影片網址，在 Mac mini 上下載，再經 Tailscale 取得私人下載連結；後續擴充字幕辨識、翻譯與燒錄。

**修改程式前必讀 `docs/PLAN.md` §2（安全守則 S1–S14）與 §12（AI 協作規範）。安全守則優先於任何功能需求。** 開發流程見 `docs/DEVELOPMENT.md`。

## 技術棧
Python 3.12、uv（build backend：`uv_build`）、yt-dlp（只用 Python API）、python-telegram-bot（async，long polling）、FastAPI + uvicorn（檔案伺服器）、SQLite（標準庫 `sqlite3` + `asyncio.to_thread`）、ffmpeg（只用參數陣列呼叫）。

## 常用指令
- 安裝依賴：`uv sync`
- 格式化 / Lint（Q1）：`uv run ruff format . && uv run ruff check --fix .`
- 型別檢查（Q2，全專案 strict）：`uv run mypy`
- 測試（Q3）：`uv run pytest -x -q`（單一檔案：`uv run pytest tests/test_x.py -q`；整合測試：`uv run pytest -m integration`）
- 危險寫法掃描（Q4）：`uv run python scripts/check_forbidden.py`
- 依賴漏洞（Q5）：`uv run pip-audit`

## 目錄結構
- `src/mediabot/`：套件本體，子套件依 `docs/PLAN.md` §7.1 在各自的里程碑才建立
- `scripts/`：開發與 CI 用的工具腳本（不屬於套件）
- `tests/`：pytest；`scripts/` 已加入 pytest 的 `pythonpath`
- `deploy/`：launchd / systemd 設定與安裝腳本（M5 之後）
- `docs/`：規劃、流程、規格（`specs/`）、ADR（`decisions/`）

## 程式碼慣例
- bot 與 worker 的業務邏輯只依賴 `JobQueue`、`Notifier` Protocol；實作由 `config.MODE` 在啟動時以 factory 選擇，不可寫死 SQLite 或 Telegram 呼叫
- Pydantic v2（`model_config`、`model_validate`）；設定用 pydantic-settings，只從 `config.py` 取得，機密用 `SecretStr`
- 所有函式加型別註記；mypy strict 必須通過
- 路徑一律用 `pathlib.Path`，由 `VAULT_DIR` 推導；不寫死作業系統專屬路徑
- 使用 `logging`，不用 `print`（`scripts/` 的 CLI 輸出除外）；log 不可包含 token、`sig=`、`Authorization`
- 錯誤用自訂例外表達，錯誤代碼使用 PLAN §8.2 定義的字串

## 資料庫規則
- SQLite 存取只出現在佇列與檔案紀錄的存取層（ADR-0002）
- Schema 以 `PRAGMA user_version` 與 `src/mediabot/db/migrations/NNN_<slug>.sql` 管理；不要修改已存在的 migration 檔，只能新增
- 時間一律存 epoch 秒（UTC，INTEGER）

## 測試
- 新功能或修 bug 必須附測試；單元測試不連網、不實際呼叫 yt-dlp 下載或 Telegram
- 業務邏輯用 Protocol 的 fake 實作測試；檔案相關測試使用 `tmp_path`
- HTTP 測試使用 `httpx.AsyncClient` + `pytest-asyncio`（`asyncio_mode = "auto"`）

## 文件位置（需要時再讀，不要一開始全部讀取）
- 規劃與安全守則：`docs/PLAN.md`
- 開發流程與品質閘門：`docs/DEVELOPMENT.md`
- 已實作的架構現況：`docs/architecture.md`
- 進度與待辦：`docs/progress.md`
- 功能規格：`docs/specs/`
- 架構決策紀錄（ADR）：`docs/decisions/`
- PR review 規則（/review 與 GitHub review 共用）：`REVIEW.md`

## Git 流程
- 分支命名：`feat/<主題>`、`fix/<主題>`、`chore/<主題>`；里程碑用 `feat/mN-<主題>`
- 不可直接 push 到 main，一律透過 PR
- Commit 訊息遵循 Conventional Commits（`feat: ...`、`fix: ...`、`refactor: ...`）

## 禁止事項
- 不要讀取或修改 `.env`、金鑰、憑證、cookie 等機密檔案
- 不要新增或升級依賴套件，除非先詢問我
- 不要手動編輯 lockfile
- 不要新增讓使用者傳入任意 yt-dlp 參數的功能、公網連入埠口、讀取瀏覽器 cookie 的功能（PLAN §12-2）
- 不要加多餘註解，不要新增未被要求的功能
- 不確定需求時先提問，不要自行假設
- 不可猜測 API、設定或參數；查不到就列出待確認事項
- 沒有實際執行過的測試，不可回報為通過

## 工作方式
- 較大的改動先用 Plan mode 或 `/plan-feature` 提出計畫，我確認後再實作
- 一次只做一個可驗收的功能；改了規格、測試流程或架構，要同步更新 `docs/`
- 完成任務前，必須執行本檔「常用指令」中的 Q1–Q4，並確認全部通過；改了依賴時加跑 Q5
- 長任務：開始時讀 `docs/progress.md`，告一段落時用 `/progress` 更新
- 大範圍搜尋程式碼交給 researcher subagent，只回報結論
- 回覆使用繁體中文；程式碼、識別名稱、commit 訊息使用英文
