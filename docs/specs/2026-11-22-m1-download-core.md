# M1 下載核心

- 狀態：實作中
- 日期：2026-11-22
- 分支：`feat/m1-download-core`（先從 `feat/m0.5-project-skeleton` 開出，PR #1 merge 後 rebase 到 `main`）
- 依據：`docs/PLAN.md` §7.3–7.5、§8.2、§11.1、§13；`docs/DEVELOPMENT.md` §10（P1–P6）

## 背景與目標

建立不依賴佇列與 Bot 的下載核心，讓 M2 的 worker 只需呼叫 `runner.run()`。

1. `config.py`：只放 M1 需要的設定（`VAULT_DIR`、`MAX_FILESIZE_BYTES`、`MAX_DURATION_SECONDS`）。
2. `security/urls.py`：`validate_url()`，並修正 P1–P3。
3. `downloader/presets.py`：`PRESETS` 白名單，只有 `video_mp4`、`audio_m4a`（P6）。
4. `downloader/runner.py`：透過 yt-dlp Python API 下載，用實際輸出路徑取代 `prepare_filename`（P5）。
5. `python -m mediabot.downloader <url> <preset>` CLI。
6. 修正 PLAN 的 P1–P6，並在 PLAN 變更紀錄記錄。

## 非目標

- 不做 `video_with_subs`（P6：`files` 表一個 job 只放一筆，字幕檔的存放方式留到 M2 或 Phase 3 決定）。
- 不定義 `Job` / `JobResult`、不做佇列、lease、重試、`JOB_TIMEOUT_SECONDS`、`MAX_CONCURRENT_JOBS`（M2）。
- 不實作 `security/signing.py`；P4 只修正 PLAN 文字（M4 實作）。
- `config.py` 不加 Telegram、簽章、Phase 2 的欄位，也不做依 `MODE` 檢查必填欄位（用到的里程碑再加）。
- 不做 log 敏感資訊過濾（M5）。

## 驗收條件

- [ ] `uv run python -m mediabot.downloader <短片網址> video_mp4` 在 Windows 開發機下載成功，輸出檔為 `DOWNLOAD_DIR/<video_id>.mp4`。
- [ ] 同一支影片用 `audio_m4a` 下載成功，回報的路徑是轉檔後實際存在的 `<video_id>.m4a`（P5）。
- [ ] `MAX_DURATION_SECONDS=1` 時下載同一支影片，以錯誤代碼 `too_long` 結束，`DOWNLOAD_DIR` 沒有留下檔案。
- [x] `test_urls.py` 涵蓋 PLAN §11.1 列出的全部合法與非法網址，外加：IP 網址回報 `ip_host`（P1）、`youtube.com:abc` 回報 `bad_port`（P2）、結尾換行或中間有空白 / 控制字元回報 `bad_chars`（P3）。
- [x] `test_presets.py`：不存在的方案丟出 `UnknownPreset`；所有方案的 opts（含 `postprocessors`）都不含 `check_forbidden.FORBIDDEN_YTDLP_KEYS` 與 `FORBIDDEN_POSTPROCESSORS`。
- [x] `test_runner.py` 以假的 YoutubeDL 測試（不連網）：opts 合併結果、直播 / 過長 / 檔案過大被拒絕、輸出路徑不在 `DOWNLOAD_DIR` 內或檔名不是 `<video_id>.<ext>` 時失敗、進度回呼的百分比。
- [x] `check_forbidden.py` 補上 `netrc_cmd`，移除 `TODO(M1)`；架構文件的對應技術債刪除。
- [ ] Q1–Q5 通過（單元部分已通過）；整合測試 `uv run pytest -m integration` 在 Windows 開發機實際執行並通過。

## 設計

### 模組與介面

```python
# errors.py
class MediabotError(Exception):
    def __init__(self, code: str, message: str = "") -> None: ...
    code: str

# config.py
class Settings(BaseSettings):            # env_file=".env", extra="ignore"
    vault_dir: Path                      # 必填，無預設值
    max_filesize_bytes: PositiveInt = 4 * 1024**3
    max_duration_seconds: PositiveInt = 10800
    @property
    def download_dir(self) -> Path: ...  # vault_dir / "downloads"
    @property
    def work_dir(self) -> Path: ...      # vault_dir / "work"
def get_settings() -> Settings: ...      # functools.cache

# security/urls.py
class InvalidURL(MediabotError): ...     # 不再繼承 ValueError（P1）
def validate_url(raw: str) -> str: ...   # 回傳 https://www.youtube.com/watch?v=<id>

# downloader/presets.py
class UnknownPreset(MediabotError): ...
@dataclass(frozen=True)
class Preset:
    label: str
    opts: Mapping[str, object]
PRESETS: Mapping[str, Preset]            # MappingProxyType，不可修改
def get_preset(name: str) -> Preset: ...

# downloader/runner.py
class DownloadFailed(MediabotError): ...
@dataclass(frozen=True)
class DownloadResult:
    video_id: str
    title: str | None
    path: Path                           # 已確認在 download_dir 內
    size_bytes: int
ProgressCallback = Callable[[float], None]   # 0.0–100.0
def run(canonical_url: str, preset: str, *, settings: Settings,
        progress_cb: ProgressCallback | None = None,
        ydl_factory: Callable[[dict[str, object]], YdlLike] = yt_dlp.YoutubeDL) -> DownloadResult: ...
```

`ydl_factory` 只供測試注入假的 YoutubeDL；`YdlLike` 是只含 `__enter__`、`__exit__`、`extract_info` 的 Protocol。

### 網址驗證（P1–P3）

依序檢查，第一個不符合的規則決定錯誤代碼：

1. 長度 > 300 → `url_too_long`（PLAN 原本用 `too_long`，與影片過長的代碼撞名，改名）。
2. 含任何空白或控制字元（`str.isspace()` 或 `unicodedata.category` 為 `C*`）→ `bad_chars`。不再 `strip()`（P3）。
3. `scheme != "https"`、有 username / password → `scheme_or_auth`。
4. 讀取 `u.port` 丟出 `ValueError`，或 port 不是 `None` → `bad_port`（P2）。
5. host 是 IP（判斷放在 `try` 之外再 raise）→ `ip_host`（P1）。
6. host 不在 `ALLOWED_HOSTS` → `host_not_allowed`。
7. 取不到 11 碼 video id → `bad_video_id`。

### 下載流程（runner）

1. `opts = BASE_OPTS | preset.opts | {match_filter, progress_hooks, logger}`。`BASE_OPTS` 照 PLAN §7.5，`paths` 由 `settings.download_dir` / `work_dir` 推導；`logger` 是把 yt-dlp 訊息轉給 `logging.getLogger("mediabot.downloader.ytdlp")` 的轉接器。執行前建立兩個目錄。
2. `match_filter`（簽章 `(info, *, incomplete) -> str | None`，已對照 yt-dlp 2026.10.26 `YoutubeDL._match_entry`）在 `incomplete=False` 時依序檢查：`is_live` / `was_live` → `live_not_supported`；`duration > max` → `too_long`；所選格式的 `filesize` 或 `filesize_approx` 總和 > 上限 → `file_too_large`。拒絕時 yt-dlp 只會略過、不會丟例外，所以 closure 先記下代碼，`extract_info` 回傳後再 `raise DownloadFailed(code)`。
3. `yt_dlp.utils.DownloadError`：`exc_info` 中是 `ExtractorError` 且 `expected=True`（影片不存在、私人影片等）→ `unavailable`（不可重試）；其他 → `download_error`（可重試）。
4. 實際路徑取 `info["requested_downloads"][0]["filepath"]`（P5），`resolve()` 後必須 `is_file()`、`is_relative_to(download_dir.resolve())`、檔名主檔名等於 `info["id"]`，否則 `output_missing`。
5. 檔案大小再檢查一次：超過上限就刪除檔案並回報 `file_too_large`（yt-dlp 的 `max_filesize` 只在 HTTP 回應有 `Content-Length` 時生效，而且超過時只會略過、不丟例外）。
6. 進度：`status == "downloading"` 時以 `downloaded_bytes / (total_bytes or total_bytes_estimate)` 換算百分比；分母不明時不回呼。

### CLI

`python -m mediabot.downloader URL PRESET`：`validate_url` → `run` → 以 `logging`（INFO，輸出到 stderr）報告路徑與大小。結束碼：0 成功；1 `DownloadFailed`；2 `InvalidURL` / `UnknownPreset` / 參數錯誤。

### 錯誤代碼（同步到 PLAN §8.2）

| 代碼 | 來源 | 可重試 |
|---|---|---|
| `url_too_long`、`bad_chars`、`scheme_or_auth`、`bad_port`、`ip_host`、`host_not_allowed`、`bad_video_id` | `validate_url` | 否 |
| `unknown_preset` | `get_preset` | 否 |
| `live_not_supported`、`too_long`、`file_too_large`、`unavailable` | runner | 否 |
| `download_error`、`output_missing` | runner | 是 |

### 資料模型變更

無（資料表在 M2）。

## 風險與待確認

- **已決定（ADR-0003）：YouTube 需要 JS runtime，採 (a)。** yt-dlp 2026.10.26 預設啟用 `js_runtimes={"deno": {}}`，並需要 `yt-dlp-ejs` 的腳本；只裝 `yt-dlp` 本體可能拿不到格式。選項：(a) `yt-dlp[default,deno]`，deno 執行檔也由 uv 鎖定（建議，額外帶入 brotli、certifi、mutagen、pycryptodomex、requests、urllib3、websockets、yt-dlp-ejs、deno）；(b) `yt-dlp[default]`，deno 由系統安裝（Mac 用 Homebrew，Windows 另裝）。無論哪種都**不啟用** `remote_components`（執行期從網路抓程式碼違反 S13）。
- `requested_downloads[0]["filepath"]` 在 `FFmpegExtractAudio` 轉檔、`MoveFiles` 之後是否為最終路徑，原始碼看起來是，但要由整合測試（`audio_m4a`）實際確認。
- `ExtractorError.expected` 能否完整區分「影片不存在」與暫時性錯誤，只能用常見情況驗證；分類錯時影響的只是 M2 是否重試。
- 整合測試需要一支短的、創用 CC 授權的公開影片網址，由擁有者提供，以環境變數 `MEDIABOT_IT_URL` 傳入；未設定時跳過。

## 實作計畫

1. [x] **依賴**：`uv add "yt-dlp[default,deno]" pydantic-settings`（ADR-0003）。驗證：`uv sync`、Q5 通過、`uv run python -c "import yt_dlp, pydantic_settings"`。
2. [x] **`errors.py`、`config.py`**：+ `tests/test_config.py`（`monkeypatch.setenv`、`_env_file=None`、`tmp_path`）。驗證：必填缺少時報錯、目錄推導、預設值；Q1–Q3。
3. [x] **`security/urls.py`**：+ `tests/test_urls.py`（parametrize，含 P1–P3 案例）。驗證：Q1–Q4。
4. [x] **`downloader/presets.py`、`check_forbidden.py` 補 `netrc_cmd`**：+ `tests/test_presets.py`、`tests/test_check_forbidden.py` 加案例。驗證：Q1–Q4。
5. [x] **`downloader/runner.py`**：+ `tests/test_runner.py`（假 YoutubeDL 依 opts 呼叫 `match_filter` / `progress_hooks`，並在 `tmp_path` 寫出檔案）。驗證：Q1–Q4。
6. [x] **`downloader/__main__.py`**：+ `tests/test_cli.py`（monkeypatch `run`，檢查結束碼）。驗證：Q1–Q4。
7. [ ] **整合測試與手動驗收**：`tests/integration/test_download.py`（`video_mp4`、`audio_m4a`、`too_long`）；手動執行 CLI。驗證：`uv run pytest -m integration` 通過，結果記錄在本檔。
8. [x] **文件**：PLAN §7.3–7.6、§8.2 修正 P1–P6 與錯誤代碼表，變更紀錄 v0.3；DEVELOPMENT.md §10 標記已處理；`docs/architecture.md`。驗證：`/review`。
