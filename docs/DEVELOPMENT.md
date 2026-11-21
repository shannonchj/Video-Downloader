# MediaBot 開發流程

> 本文件定義「怎麼開發」：環境、每個里程碑的工作循環、品質閘門、測試策略與 AI 協作方式。
> 「要做什麼」以 [`PLAN.md`](PLAN.md) 為準；兩者衝突時，安全守則（PLAN §2）優先，其餘以 PLAN 為準並回頭修正本文件。

- 文件版本：v0.1（2026-11-22）
- 狀態：已確認（2026-11-22，§12 全部項目採建議方案）

---

## 1. 文件體系

| 文件 | 角色 | 何時更新 |
|---|---|---|
| `docs/PLAN.md` | 總體規劃、安全守則、介面定義（單一事實來源） | 架構或守則改變時；末尾變更紀錄加一行 |
| `docs/DEVELOPMENT.md` | 本文件：開發流程 | 流程、工具、品質閘門改變時 |
| `docs/specs/YYYY-MM-DD-mN-<slug>.md` | 每個里程碑一份規格與實作計畫（由 `/plan-feature` 產生） | 里程碑開始前撰寫、確認；實作中只更新勾選與發現 |
| `docs/decisions/NNNN-<slug>.md` | ADR：偏離 PLAN 或重大技術選擇 | 換套件、改資料模型、改架構時 |
| `docs/architecture.md` | 「已實作」的架構現況（PLAN 是藍圖，這份是實況） | 每個里程碑合併時同步 |
| `docs/progress.md` | 跨 session 工作記憶（≤ 40 行） | 每次告一段落用 `/progress` |
| `CLAUDE.md` / `REVIEW.md` | AI 工作規則與 review 規則 | 規則改變時 |

原則：同一件事只寫在一處，其他地方用連結或節號引用。

---

## 2. 開發環境

### 2.1 兩種環境

| 項目 | 開發機（Windows 11） | 正式環境（Mac mini，Phase 1） |
|---|---|---|
| 用途 | 撰寫程式、單元測試、CLI 手動下載測試 | 常駐服務、整合測試、7 天穩定性驗證 |
| Python | 3.12（uv 管理的 venv） | 3.12（uv 管理的 venv，帳號 `mediabot`） |
| ffmpeg | winget 版（已安裝 8.0） | Homebrew |
| Telegram Bot | **測試用 Bot**（另向 BotFather 申請） | 正式 Bot |
| 檔案伺服器 | `127.0.0.1:8080`，本機瀏覽器測試 | `127.0.0.1:8080` + `tailscale serve` |
| launchd / pmset / Tailscale | 無法測試 | M0、M4、M5 在此驗證 |

### 2.2 跨平台規則

- 路徑一律用 `pathlib.Path`，不寫死 `/` 或 `\`；所有路徑由 `config.VAULT_DIR` 推導。
- 不呼叫 macOS 專屬指令（`pmset`、`launchctl`）於應用程式碼中；這些只出現在 `deploy/macos/`。
- 測試不依賴作業系統：檔案權限檢查（`600`/`700`）只在 POSIX 上執行，Windows 以 `pytest.mark.skipif` 略過並註明原因。
- 開發機的 `.env` 由擁有者自行建立（AI 不讀取、不修改，見 CLAUDE.md 禁止事項）；`.env.example` 是唯一可提交的範本。

### 2.3 專案初始化（M0.5，見 §6）

```bash
uv sync                          # 建立 venv 並安裝鎖定版本
uv run pytest -x -q              # 測試
uv run ruff check --fix . && uv run ruff format .
uv run python scripts/check_forbidden.py
uv run mypy                      # 全專案 strict
```

---

## 3. 里程碑工作循環

每個里程碑（PLAN §13 的 M1、M2…）都走同一個循環。**一次只進行一個里程碑**；里程碑太大時拆成多個 PR，但每個 PR 都必須可獨立驗收。

```
① 規劃 ──▶ ② 確認 ──▶ ③ 開分支 ──▶ ④ 測試先行 ──▶ ⑤ 實作 ──▶ ⑥ 品質閘門
                                                                    │
⑩ 更新進度 ◀── ⑨ 合併 ◀── ⑧ PR + GitHub Claude review ◀── ⑦ 本機 /review
```

| 步驟 | 執行者 | 內容 | 產出 |
|---|---|---|---|
| ① 規劃 | AI（`/plan-feature`） | 依 PLAN 對應章節撰寫規格；列出不明確處（≤ 5 題）；實作計畫拆成可單獨測試的小步驟 | `docs/specs/…md`（狀態：草稿） |
| ② 確認 | 擁有者 | 回答問題、修改或核准規格 | 規格狀態改為「已確認」 |
| ③ 開分支 | AI | `feat/mN-<slug>`（例：`feat/m1-url-validation`） | 分支 |
| ④ 測試先行 | AI（可交給 `test-writer`） | 先寫 PLAN §11 列出的測試案例，確認它們**失敗** | 失敗的測試 |
| ⑤ 實作 | AI | 依實作計畫逐步完成；每完成一步就跑相關測試並在規格勾選 | 程式碼 |
| ⑥ 品質閘門 | AI | §4 全部項目，須實際執行並附結果 | 通過紀錄 |
| ⑦ 本機 review | AI（`/review` → `code-reviewer`） | 依 `REVIEW.md` 審查；🔴 項目經擁有者同意後修正 | 審查結果 |
| ⑧ PR | 擁有者輸入 `/ship` | commit、push、開 PR；GitHub Action 自動跑 Claude review（最多 3 輪） | PR |
| ⑨ 合併 | **擁有者** | 人工確認後 squash merge 到 `main` | `main` 更新 |
| ⑩ 更新進度 | AI（`/progress`） | 更新 `progress.md`、PLAN §13 勾選、`architecture.md` | 文件 |

需要在 Mac mini 上驗證的里程碑（M0、M4、M5），步驟 ⑥ 之後增加「部署驗證」：由擁有者在 Mac mini 依規格中的驗收條件手動執行，結果寫回規格。

### 3.1 何時停下來問擁有者

- 需求必須違反安全守則（PLAN §12-1）。
- 要新增或升級依賴（CLAUDE.md 禁止事項）。
- PLAN 內容有錯、互相矛盾或查不到官方依據（PLAN §12-9）。
- 實作中發現規格需要改動 → 先改規格、請擁有者確認，再繼續寫程式。

---

## 4. 品質閘門（Definition of Done）

一個 PR 只有在下列項目**實際執行且全部通過**後才算完成。沒執行過的項目不可回報為通過。

| # | 檢查 | 指令 / 方式 | 範圍 |
|---|---|---|---|
| Q1 | 格式與 lint | `uv run ruff format --check . && uv run ruff check .` | 全部 |
| Q2 | 型別 | `uv run mypy`（全專案 strict，範圍為 `src/`、`scripts/`；M0.5 決定） | 全部 |
| Q3 | 單元測試 | `uv run pytest -x -q` | 全部 |
| Q4 | 危險寫法掃描 | `uv run python scripts/check_forbidden.py`（取代 PLAN §11.3 的 `rg`，見 §5.2） | `src/` |
| Q5 | 依賴漏洞 | `uv run pip-audit`（有改依賴的 PR 必跑；其餘每週一次） | 依賴 |
| Q6 | 文件同步 | 規格勾選、PLAN §13、`architecture.md`、PLAN 變更紀錄（有改架構時） | 文件 |
| Q7 | 安全守則對照 | PR 描述列出本次涉及的 S 編號及其驗證方式（§5.1） | PR |

發版前（M5 及之後每次部署）另外執行 PLAN §11.3 的完整安全檢查清單。

---

## 5. 安全守則的落實方式

### 5.1 守則 → 驗證手段

每條守則至少有一種**自動化**驗證；無法自動化的列入發版檢查清單。

| 守則 | 自動化驗證 | 手動 / review |
|---|---|---|
| S1 不開公網埠 | — | 發版清單：tailnet 外連不到 |
| S2 只綁 127.0.0.1 | `test_config`：`FILESERVER_BIND` 非 loopback 時啟動失敗 | `tailscale serve status` |
| S3 不收任意 yt-dlp 參數 | `test_presets`：未知方案丟例外；所有 opts 不含禁止鍵；bot 只接受 preset 名稱 | review |
| S4 不經 shell | Q4 掃描 `shell=True`、`os.system`、`os.popen`、`subprocess` 字串參數 | review |
| S5 網址驗證 | `test_urls`（PLAN §11.1 全部案例 + §8 補充案例） | — |
| S6 使用者白名單 | `test_bot_auth`：非白名單、群組皆無回覆、無任務 | 發版清單：另一帳號測試 |
| S7 簽章連結 | `test_signing`、`test_fileserver` | — |
| S8 檔名不用標題 | `test_runner`：outtmpl 固定為 `%(id)s.%(ext)s`；`files.rel_path` 不含標題 | — |
| S9 機密不外洩 | `test_logging`：token / `sig=` / `Authorization` 被遮蔽；`config` 的 repr 不含機密（`SecretStr`） | `.gitignore`、hook 已保護 `.env` |
| S10 非管理員帳號 | — | M0 / M5 部署驗證 |
| S11 不用瀏覽器 cookie | `test_presets` 禁止鍵；Q4 掃描 `cookiesfrombrowser` | — |
| S12 資源上限 | `test_runner`（match_filter）、`test_ratelimit`、`test_worker`（並行數、逾時） | — |
| S13 鎖版與更新 | `uv.lock` 進 git；Q5 | 每週更新流程（§7.2） |
| S14 VPS 不存影片/cookie | `test_config`：`hybrid-vps` 模式下設定 cookie 或 VAULT 下載路徑即失敗 | M7 部署驗證 |

### 5.2 為什麼用腳本取代 `rg` 掃描

PLAN §11.3 的 `rg "…|exec" src/` 會命中 `executor`、`execute` 等正常字詞而產生大量誤報，開發機也不一定有 `rg`。改用 `scripts/check_forbidden.py`：以 Python `ast` 檢查呼叫（`os.system`、`subprocess.*(shell=True)`、`eval`/`exec` 內建函式），並以字串比對檢查 yt-dlp 禁止鍵（`exec`、`exec_before_download`、`cookiesfrombrowser`、`cookiefile`、`external_downloader`），在 CI 與本機都可執行。

---

## 6. 里程碑執行順序

在 PLAN §13 的 M1 之前插入 **M0.5 專案骨架**，先讓工具鏈與規則就位。

| 順序 | 里程碑 | 主要內容 | 在哪驗證 | 驗收重點 |
|---|---|---|---|---|
| 1 | **M0.5 專案骨架** | `pyproject.toml`、src 目錄、ruff/mypy/pytest 設定、`.env.example`、`scripts/check_forbidden.py`、GitHub Actions CI、對齊 CLAUDE.md（§9） | Windows | `uv sync` 後 Q1–Q4 全綠（測試僅 smoke test） |
| 2 | M1 下載核心 | `config.py`、`models.py`、`security/urls.py`、`downloader/` | Windows | `uv run python -m mediabot.downloader <url> video_mp4` 成功 |
| 3 | M2 佇列與 Worker | `queue/base.py`、`sqlite_queue.py`、`worker/main.py`、清理 | Windows | 狀態轉換、lease、重試測試通過 |
| 4 | M3 Telegram Bot | `bot/`、`security/ratelimit.py`、`notify/telegram.py` | Windows（測試 Bot） | 測試 Bot 端到端：傳網址 → 下載完成通知 |
| 5 | M4 檔案伺服器 | `security/signing.py`、`fileserver/app.py` | Windows → Mac mini | 本機點連結下載成功；Mac mini 經 Tailscale 下載成功 |
| 6 | M0 環境建置 | PLAN §4.5–4.6（擁有者在 Mac mini 執行） | Mac mini | 可與 M1–M4 並行，最晚在 M4 部署驗證前完成 |
| 7 | M5 維運強化 | plist、`install.sh`、更新排程、日誌過濾、備份、發版清單 | Mac mini | 連續穩定運作 7 天 |
| 8+ | M6–M12 | 依 PLAN §13；各自開始前再寫規格 | — | — |

說明：
- M0 是純系統設定，由擁有者在 Mac mini 執行，AI 只負責產出步驟檢查表，因此不阻擋 M1–M3 在 Windows 上開發。
- M3 先於 M4：M3 的完成通知先只回覆「下載完成 + file_id」，M4 再補上簽章連結。
- Phase 2、3 介面（`JobQueue`、`Notifier`、`pipeline.hooks`）在 M1–M4 就依 PLAN §7.2 建立，避免日後重構。

---

## 7. 依賴管理

### 7.1 初始依賴（**待擁有者核准**）

| 套件 | 用途 | 里程碑 |
|---|---|---|
| `yt-dlp` | 下載 | M1 |
| `pydantic`、`pydantic-settings` | 設定與資料模型 | M1 |
| `python-telegram-bot` (v21+) | Bot | M3 |
| `fastapi`、`uvicorn` | 檔案伺服器 | M4 |
| `aiosqlite` | 非同步 SQLite（或改用標準庫 `sqlite3` + `asyncio.to_thread`，見 §10 Q3） | M2 |
| 開發用：`pytest`、`pytest-asyncio`、`httpx`、`ruff`、`mypy`、`pip-audit` | 測試與品質閘門 | M0.5 |

依賴只在需要它的里程碑才加入；新增時在 PR 描述說明理由（PLAN §12-7）。一律用 `uv add` / `uv lock`，不手動編輯 `uv.lock`。

### 7.2 yt-dlp 每週更新與「鎖定版本」的衝突

PLAN S13 要求鎖版，§10.1 卻在 Mac mini 上直接 `pip install -U yt-dlp`，會讓正式環境與 `uv.lock` 不一致。建議做法：

- **開發端**：每週（或下載開始失敗時）執行 `uv lock --upgrade-package yt-dlp`，跑完 Q3 後走一般 PR 流程。
- **Mac mini**：`mediabot-update` 排程改為 `git pull` + `uv sync --frozen` + 重啟服務，只安裝 `main` 上已鎖定的版本。
- 緊急情況（YouTube 改版導致全部失敗）允許在 Mac mini 手動升級，但事後必須補 PR 讓 lock 一致。

此為偏離 PLAN 的決定，確認後寫成 ADR-0001。

---

## 8. 測試策略

| 層級 | 範圍 | 規則 |
|---|---|---|
| 單元測試（預設） | 全部模組 | **不連網、不呼叫真實 yt-dlp 下載、不呼叫 Telegram**；用 `tmp_path` 當 VAULT；時間相關用可注入的 `clock` |
| 整合測試 `-m integration` | 真實 yt-dlp、真實測試 Bot | 預設不執行；需手動 `uv run pytest -m integration`，使用 CC 授權短片 |
| 部署驗證 | Mac mini | 依規格中的驗收條件手動執行並記錄 |

替身（fakes）設計：
- `FakeQueue`、`FakeNotifier` 實作 `JobQueue` / `Notifier` Protocol，用來測 bot 與 worker 的業務邏輯——這同時驗證了「業務邏輯只依賴 Protocol」（PLAN §12-4）。
- yt-dlp 以 monkeypatch `yt_dlp.YoutubeDL` 替換，驗證傳入的 opts（禁止鍵、outtmpl、match_filter），而不是真的下載。
- Telegram handler 以 python-telegram-bot 的 `Update` 物件建構測試輸入。

---

## 9. 現有設定與 PLAN 的落差（M0.5 一併處理）

目前的 `CLAUDE.md`、`.claude/settings.json`、`REVIEW.md` 來自通用範本，與 PLAN 不一致。**AI 依 CLAUDE.md 工作，若不先修正，後續每次實作都會被錯誤規則誤導。**

| 檔案 | 現況 | 需修改為 |
|---|---|---|
| `CLAUDE.md` 專案概述 | `<專案名稱>` 佔位 | MediaBot 一句話描述 |
| `CLAUDE.md` 技術棧 | FastAPI + SQLAlchemy + PostgreSQL + Alembic | Python 3.12 + yt-dlp + python-telegram-bot + FastAPI + SQLite，uv |
| `CLAUDE.md` 常用指令 | `fastapi dev app/main.py`、docker、alembic | 各程序啟動指令、`mypy src/mediabot`、Q4 腳本 |
| `CLAUDE.md` 目錄結構 / 慣例 | `app/api`、`repositories`、SQLAlchemy | PLAN §7.1 的 `src/mediabot/`；Protocol + factory 原則 |
| `CLAUDE.md` 資料庫規則 | migration、PostgreSQL、`TIMESTAMP WITH TIME ZONE` | SQLite schema 版本管理方式（見 §10 Q4）；時間存 epoch 秒（PLAN §8.1） |
| `CLAUDE.md` | 無安全守則 | 加一行：「修改程式前必讀 `docs/PLAN.md` §2、§12」 |
| `.claude/settings.json` | 允許 alembic、docker | 移除；加入 `uv run python scripts/check_forbidden.py`、`uv run pip-audit` |
| `REVIEW.md` | Important 條件有 TODO | 加入：違反 S1–S14 任一條即為 Important |
| `.github/workflows/` | 只有 Claude review | 新增 `ci.yml`：Q1–Q4（Ubuntu + Windows 矩陣） |
| Git | 本機在 `master`、無任何 commit、無 remote；設定中主分支為 `main` | 改名為 `main`，建立初始 commit，建立 GitHub 私有 repo（§10 Q1） |

---

## 10. PLAN.md 中發現、實作前需修正的問題

實作對應里程碑時一併修正 PLAN，並在 PLAN 變更紀錄記錄。

P1–P6 已於 M1 修正（PLAN v0.3）；P7、P8 已於 M0.5 處理。

| # | 位置 | 問題 | 建議 |
|---|---|---|---|
| P1 | §7.3 `validate_url` | `InvalidURL` 繼承 `ValueError`，在 `try` 內 `raise InvalidURL("ip_host")` 會被同一個 `except ValueError` 吞掉，IP 網址的錯誤代碼變成 `host_not_allowed` | IP 判斷移到 `try` 之外（先用 `try` 判斷是否為 IP，再於外面 raise） |
| P2 | §7.3 | `u.port` 遇到非數字 port（`youtube.com:abc`）會丟出 `ValueError`，不是 `InvalidURL` | 包成 `InvalidURL("bad_port")` |
| P3 | §7.3 | `raw.strip()` 會吃掉頭尾換行，`"https://youtu.be/xxxxxxxxxxx\n"` 會被接受；中間的控制字元則交給 `urlparse` 處理，行為不明確 | 先拒絕任何控制字元與空白，再解析 |
| P4 | §7.6 `verify_link` | 呼叫未定義的 `sign_link_raw` | 抽出 `_compute_sig(file_id, exp)` 供兩者共用 |
| P5 | §7.5 | `prepare_filename` 在轉檔後副檔名不準（PLAN 已註記）；`audio_m4a` 預設的 postprocessor 會改副檔名 | 以 `info["requested_downloads"][0]["filepath"]` 取得實際路徑，並確認在 `DOWNLOAD_DIR` 內 |
| P6 | §7.4 `video_with_subs` | 字幕會產生額外檔案，`files` 表一個 job 一筆的設計放不下 | M1 規格中決定：字幕另存一筆 `files`，或 M1 先不做此方案 |
| P7 | §10.1 | 更新 yt-dlp 的方式與 S13 衝突 | 見 §7.2 |
| P8 | §11.3 | `rg … exec` 誤報 | 見 §5.2 |

---

## 11. AI 協作分工速查

| 情境 | 使用 |
|---|---|
| 開始新里程碑 | `/plan-feature <里程碑與 PLAN 章節>` |
| 大範圍查程式碼 | `researcher` subagent |
| 先寫測試 / 補測試 | `test-writer` subagent |
| commit 前審查 | `/review`（內部使用 `code-reviewer`） |
| commit + push + 開 PR | 擁有者輸入 `/ship`（AI 不自行觸發） |
| 告一段落、準備 `/clear` | `/progress` |
| 重大技術選擇 | 依範本新增 `docs/decisions/NNNN-*.md` |

AI 不做的事：merge PR、push 到 `main`、讀寫 `.env`、在 Mac mini 上執行 `sudo` 指令、未經同意新增依賴。

---

## 12. 確認事項

> 2026-11-22 擁有者已全部同意：建立 GitHub 私有 repo、採用 §6 順序、使用標準庫 `sqlite3`、以 `PRAGMA user_version` 管理 schema、核准 §7.1 依賴、採用 §7.2 更新方式、於 M0.5 修正 §9 設定檔、另申請測試 Bot。

1. **Q1 Git 遠端**：是否建立 GitHub 私有 repo？（GitHub Action 的 Claude review 與 CI 都需要；若不用 GitHub，§3 步驟 ⑧ 改為只做本機 review。）
2. **Q2 本文件 §6 順序**：同意插入 M0.5，且 M1–M3 先在 Windows 開發、M0 由您在 Mac mini 並行處理？
3. **Q3 SQLite 存取**：使用 `aiosqlite`（多一個依賴），或標準庫 `sqlite3` + `asyncio.to_thread`（零依賴）？建議後者。
4. **Q4 Schema 版本管理**：不使用 Alembic，改用 `PRAGMA user_version` + `src/mediabot/db/migrations/NNN_*.sql` 依序套用？
5. **Q5 依賴清單**：§7.1 是否核准？
6. **Q6 yt-dlp 更新方式**：同意 §7.2（開發端升級 lock → PR → Mac mini `uv sync --frozen`）？
7. **Q7 §9 的設定檔修正**：同意在 M0.5 中改寫 `CLAUDE.md`、`settings.json`、`REVIEW.md`？
8. **Q8 測試用 Telegram Bot**：開發期間另外申請一個測試 Bot？
