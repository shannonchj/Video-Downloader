# 架構說明

<!-- 「已實作」的架構現況；藍圖見 docs/PLAN.md。每個里程碑合併時同步更新 -->

## 系統概觀
目前完成到 M1（下載核心）：可用 CLI 驗證網址並以白名單方案下載，尚無佇列、Bot、檔案伺服器。目標架構見 `docs/PLAN.md` §4（Phase 1）。

## 模組與職責
| 模組 | 職責 | 備註 |
|---|---|---|
| `src/mediabot/__init__.py` | 套件根目錄，提供 `__version__` | 子套件在各自的里程碑建立 |
| `src/mediabot/errors.py` | `MediabotError(code, message)`，錯誤代碼見 PLAN §8.2 | 各模組的例外都繼承它 |
| `src/mediabot/config.py` | `Settings`（pydantic-settings）：`VAULT_DIR`、`MAX_FILESIZE_BYTES`、`MAX_DURATION_SECONDS`；推導 `download_dir`、`work_dir` | 只放已用到的欄位，其餘在各里程碑加入；`extra="ignore"` |
| `src/mediabot/security/urls.py` | `validate_url()`（PLAN §7.3） | 只接受 YouTube，回傳標準化網址 |
| `src/mediabot/downloader/presets.py` | `PRESETS`：`video_mp4`、`audio_m4a` | 唯讀；`build_opts()` 回傳深拷貝 |
| `src/mediabot/downloader/runner.py` | `run()`：yt-dlp Python API 下載，回傳 `DownloadResult` | 同步函式；`ydl_factory` 供測試注入假物件 |
| `src/mediabot/downloader/__main__.py` | CLI `python -m mediabot.downloader URL PRESET` | 從 `.env` / 環境變數讀設定 |
| `scripts/check_forbidden.py` | 以 `ast` 掃描 PLAN S3/S4/S11 禁止的寫法（Q4） | 只用標準庫；不提供忽略註解 |

## 資料模型
尚未實作（M2，見 ADR-0002）。

## 外部依賴
- 執行期：`yt-dlp[default,deno]`（含 yt-dlp-ejs 與 deno 執行檔，YouTube 解析需要 JS runtime；不啟用 `remote_components`）、`pydantic-settings`。系統需有 ffmpeg。
- 開發：pytest、pytest-asyncio、httpx、ruff、mypy、pip-audit（版本見 `uv.lock`）。

## 部署與環境
- 開發：Windows 11 + uv 0.13.6 + Python 3.12。
- CI：GitHub Actions `ci.yml`（Ubuntu + Windows，Q1–Q4）、`audit.yml`（pip-audit，每週與依賴變更時）。
- 正式環境：尚未部署（Mac mini，M0 / M5）。

## 已知限制與技術債
- `check_forbidden.py` 無法偵測以下寫法，由 review 把關：動態組成的鍵（`opts["ex" + "ec"]`）、`getattr(os, "system")`、`__import__("os")`、先存進變數的指令字串、`**{"shell": True}` 展開。
- 下載中斷時 `work/` 可能留下暫存檔，清理在 M2（PLAN §10.4）。
- yt-dlp 因 `max_filesize` 略過下載而預估大小不明時，回報的是 `output_missing`（可重試）而不是 `file_too_large`。
