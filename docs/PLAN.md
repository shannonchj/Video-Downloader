# MediaBot 專案規劃書

> 自架影片下載 → 字幕辨識 → 中文翻譯 → 燒錄輸出 的個人工具
> 本文件供人類與 AI 協作者共同參考。**AI 協作者修改程式前請先閱讀第 2 節「安全守則」與第 12 節「AI 協作規範」。**

- 文件版本：v0.2（2026-11-22）
- 主要語言：Python 3.12
- 目標語種：菲律賓語（Tagalog / Taglish）、英文 → 台灣繁體中文

---

## 目錄

1. 專案目標與範圍
2. 安全守則（不可違反）
3. 硬體與部署方案總覽
4. Phase 1：Mac mini 單機架構（主要方案）
5. Phase 2：VPS + Mac mini 混合架構（進階切換方案）
6. Phase 3：字幕辨識與翻譯流水線（預留）
7. 模組設計與介面定義
8. 資料模型
9. 設定檔與模式切換
10. 部署與維運
11. 測試計畫
12. AI 協作規範
13. 里程碑與任務清單
14. 已知限制與待確認事項

---

## 1. 專案目標與範圍

### 1.1 目標

1. 在任何裝置（手機、平板、筆電）透過 **Telegram Bot** 傳送影片網址，即可自動下載影片。
2. 下載完成後，Bot 回覆一個**僅限私人網路（Tailscale）可開啟**的下載連結。
3. 後續擴充：自動產生原文字幕 → 翻譯為台灣繁體中文 → 燒錄進影片輸出。
4. 架構需能從「Mac mini 單機」平順切換為「VPS 收指令 + Mac mini 執行」的混合模式。

### 1.2 不在範圍內

- 公開給他人使用的服務（本系統僅供擁有者本人）。
- 繞過平台的 DRM、付費牆或登入保護。
- 住宅代理、IP 偽裝等反封鎖手段。

### 1.3 使用規範

僅下載擁有者有權使用的內容（自己的影片、取得授權或允許下載的素材），並遵守各平台服務條款。

---

## 2. 安全守則（不可違反）

以下規則適用於所有階段、所有模組。任何程式碼變更若違反其中一條，視為缺陷。

| # | 規則 | 理由 |
|---|---|---|
| S1 | **不開放任何公網連入埠口**。不做 port forwarding、不使用需要公開 webhook 的平台（例如 LINE）。 | 消除絕大部分外部攻擊面 |
| S2 | 所有自建 HTTP 服務只綁定在 `127.0.0.1`，並透過 `tailscale serve` 提供給 tailnet 內的裝置。 | 只有自己的裝置能存取 |
| S3 | **禁止讓使用者傳入任意 yt-dlp 參數**。只能從後端定義的 `PRESETS` 中選擇。 | `--exec` 等參數可執行任意指令 |
| S4 | **禁止透過 shell 執行外部指令**。不可使用 `os.system`、`subprocess(..., shell=True)` 或字串拼接指令；yt-dlp 一律使用 Python API，ffmpeg 一律使用參數陣列。 | 防止指令注入 |
| S5 | 網址必須通過 `security.urls.validate_url()`：限 `https`、網域白名單、長度上限、禁止內網 IP 和帳密格式（`user@host`）。 | 防止 SSRF 與惡意輸入 |
| S6 | Bot 只回應 `ALLOWED_USER_IDS` 白名單內的使用者，而且只處理私訊。陌生人一律**完全不回應**，只記錄 user id。 | Bot 是公開可搜尋的 |
| S7 | 檔案下載連結使用 **HMAC 簽章加上有效期限**。檔案伺服器用 `file_id` 查資料庫取得路徑，**絕不使用 URL 中的路徑字串**。 | 防止路徑穿越與連結外流 |
| S8 | 輸出檔名一律為 `{video_id}.{ext}` 或 UUID，不使用影片標題。 | 防止特殊字元與路徑穿越 |
| S9 | 機密資訊（Bot Token、HMAC 金鑰）只存放在權限 `600` 的 `.env`，**不寫進程式碼、不提交到 git、不輸出到日誌**。 | 避免外洩 |
| S10 | 服務以專用的**非管理員**帳號 `mediabot` 執行，只能寫入 `~mediabot/MediaVault/`。 | 被入侵時限縮損害 |
| S11 | **不使用 `--cookies-from-browser`**，也不讀取擁有者主要瀏覽器的資料。若未來確實需要 cookie，只能用專用小帳號匯出的單一 cookie 檔，權限設為 `600`。 | 保護個人帳號 |
| S12 | 資源上限：單檔大小上限、影片長度上限、同時執行任務數上限、每位使用者每小時任務數上限。 | 防止塞爆磁碟或濫用 |
| S13 | 依賴套件須鎖定版本，並定期更新（yt-dlp 每週更新），也要定期執行 `pip-audit`。 | 修補已知漏洞 |
| S14 | Phase 2 的 VPS 上**不存放影片、不存放 cookie**，只存放任務佇列的資料（網址與狀態）。 | VPS 被入侵時損失最小 |

---

## 3. 硬體與部署方案總覽

| 項目 | Phase 1（主要方案） | Phase 2（進階方案） |
|---|---|---|
| 接收指令（Bot） | Mac mini | 免費 VPS（GCP e2-micro 或 Oracle Always Free） |
| 任務佇列 | Mac mini 本機 SQLite | VPS 上的 Queue API 與 SQLite |
| 下載執行（yt-dlp） | Mac mini（住宅 IP） | Mac mini（住宅 IP，醒著時主動拉取任務） |
| 檔案儲存與下載連結 | Mac mini | Mac mini |
| 字幕辨識（Phase 3） | Mac mini（Apple Silicon 加速） | Mac mini |
| Mac mini 睡眠 | 關閉系統睡眠（螢幕可關閉） | 可以睡眠，定時喚醒處理任務 |
| 私人網路 | Tailscale | Tailscale（VPS 也加入 tailnet） |

**為什麼下載一定要在 Mac mini 上執行？** YouTube 對資料中心 IP（AWS、GCP、Azure、各家 VPS）的檢查非常嚴格，常出現 `Sign in to confirm you're not a bot` 錯誤。家用網路的住宅 IP 不會有這個問題。因此不論哪個階段，**yt-dlp 都只在 Mac mini 上執行**。

---

## 4. Phase 1：Mac mini 單機架構（主要方案）

### 4.1 架構圖

```
┌─────────────── 使用者裝置（手機/平板/筆電，已安裝 Tailscale + Telegram）───────────────┐
│  ① 在 YouTube App 按分享 → 傳給 Telegram Bot                                         │
│  ⑤ 點 Bot 回覆的連結 → 透過 Tailscale 從 Mac mini 下載                                 │
└──────────────────────────────────────────────────────────────────────────────────────┘
          │ ①                                                        ▲ ⑤ HTTPS（tailnet 內）
          ▼                                                          │
   Telegram 伺服器  ◀── ② long polling（Mac mini 主動連出）           │
                                   │                                 │
┌──────────────────────── Mac mini（使用者：mediabot）────────────────┼─────────────┐
│                                  ▼                                  │             │
│  ┌────────────┐  enqueue  ┌──────────────┐  claim   ┌────────────┐ │             │
│  │ bot        │─────────▶│ queue        │◀─────────│ worker     │ │             │
│  │ (Telegram) │           │ (SQLite)     │          │ (yt-dlp)   │ │             │
│  └────────────┘           └──────────────┘          └─────┬──────┘ │             │
│        ▲  ④ 完成通知 + 簽章連結                            │ ③ 下載  │             │
│        └──────────────────────────────────────────────────┤        │             │
│                                                            ▼        │             │
│                                              ~/MediaVault/downloads │             │
│                                                            │        │             │
│  ┌──────────────────────────┐  只綁 127.0.0.1:8080          │        │             │
│  │ fileserver (FastAPI)     │◀─────────────────────────────┘        │             │
│  └──────────────────────────┘                                       │             │
│              ▲  tailscale serve（HTTPS, *.ts.net 憑證）──────────────┘             │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### 4.2 元件清單

| 元件 | 技術 | 職責 |
|---|---|---|
| `bot` | python-telegram-bot v21+（async，long polling） | 驗證使用者、解析網址、建立任務、回覆狀態 |
| `queue` | SQLite（WAL 模式） | 任務的建立、領取、完成與失敗紀錄 |
| `worker` | yt-dlp Python API、ffmpeg | 逐一執行下載任務，完成後呼叫通知模組 |
| `fileserver` | FastAPI + uvicorn | 驗證簽章，以串流方式回傳檔案 |
| `notify` | Telegram Bot API | 將完成或失敗訊息傳回給使用者 |
| Tailscale | Homebrew 版 `tailscale`（系統常駐 daemon） | 私人網路，以及透過 `tailscale serve` 提供 HTTPS |

### 4.3 執行方式的決策

- Phase 1 **不使用 Docker**，以專用帳號 `mediabot` 搭配 Python venv，由 `launchd` LaunchDaemon 執行。
  - 理由：macOS 上的 Docker Desktop 需要有使用者登入 GUI 才會啟動，不適合當作開機自動啟動的常駐服務；而且 Docker 在 macOS 上無法使用 Metal GPU，Phase 3 的 Whisper 還是得在原生環境執行。
  - 隔離方式：非管理員帳號、資料夾權限 `700`、Python 程式不具任何 sudo 權限。
- 三個常駐程序：`mediabot-bot`、`mediabot-worker`、`mediabot-fileserver`（各自一個 plist）。
- 一個排程任務：`mediabot-update`（每週更新 yt-dlp）。

### 4.4 主要流程

1. 使用者傳送網址給 Bot。
2. Bot 檢查 `user_id ∈ ALLOWED_USER_IDS`、確認是私訊，並檢查使用頻率限制。
3. 用 `validate_url()` 驗證網址，抽取出標準化的網址（`canonical_url`）。
4. Bot 顯示 InlineKeyboard 讓使用者選擇預設方案（影片 MP4 / 只要音訊 / 影片加原生字幕）。
5. 呼叫 `queue.enqueue(Job)`，並回覆「已加入佇列（第 N 位）」。
6. Worker 輪詢 `queue.claim()`，取得任務後執行 `downloader.run(job)`。
7. 下載前先用 `extract_info(download=False)` 檢查影片長度、是否為直播、檔案大小預估。超過上限就直接標記為失敗。
8. 下載完成後寫入檔案紀錄（`files` 表），並產生簽章連結。
9. `notify.job_done(job, link)`：Bot 回覆連結。小於 45 MB 的音訊或字幕檔可以額外直接傳送。
10. Phase 3 擴充點：`pipeline.hooks.on_download_complete(job, file)`。

### 4.5 Mac mini 系統設定

```bash
# 電源（管理員帳號執行）
sudo pmset -a sleep 0          # 關閉系統睡眠
sudo pmset -a displaysleep 10  # 螢幕 10 分鐘後關閉
sudo pmset -a disksleep 10     # 硬碟可以休眠
sudo pmset -a autorestart 1    # 停電後自動開機
sudo pmset -a womp 1           # 允許網路喚醒

# 防火牆：開啟並啟用隱形模式
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setglobalstate on
sudo /usr/libexec/ApplicationFirewall/socketfilterfw --setstealthmode on

# 專用帳號（非管理員）
sudo sysadminctl -addUser mediabot -fullName "MediaBot Service" -password -   # 互動輸入密碼
sudo mkdir -p /Users/mediabot/MediaVault/{downloads,work,db,logs}
sudo chown -R mediabot:staff /Users/mediabot/MediaVault
sudo chmod -R 700 /Users/mediabot/MediaVault

# 相依工具（管理員帳號用 Homebrew 安裝，所有帳號都能執行）
brew install python@3.12 ffmpeg tailscale
sudo brew services start tailscale      # 系統層級的 tailscaled，不需要登入 GUI
sudo tailscale up --ssh=false
```

其他系統設定：

- **FileVault：** 保持開啟。代價是停電重開機後，必須有人登入一次解鎖磁碟，服務才會啟動（見第 14 節）。
- **自動更新：** 開啟 macOS 安全性更新。
- **遠端存取：** 不開啟「遠端登入（SSH）」；若需要，只允許金鑰登入，並且只在 tailnet 內使用。

### 4.6 Tailscale 設定

- 擁有者的所有裝置與 Mac mini 加入同一個 tailnet。
- 在 Tailscale 管理後台：
  - 開啟 MagicDNS 與 HTTPS 憑證功能。
  - 設定 ACL，只允許擁有者的裝置存取 Mac mini 的 443 埠。
  - 關閉 Mac mini 的金鑰到期，或者記錄到期日期。
- 提供檔案服務：

```bash
sudo tailscale serve --bg 8080
# 之後的網址為 https://<mac-mini 名稱>.<tailnet>.ts.net/
```

---

## 5. Phase 2：VPS + Mac mini 混合架構（進階切換方案）

### 5.1 目的

讓 Mac mini 可以睡眠或關機，同時 Bot 仍然 24 小時在線接收網址。Mac mini 醒來後，自動處理累積的任務。

### 5.2 架構圖

```
手機 Telegram ──▶ Telegram 伺服器 ◀── long polling ── ┌──── VPS（加入 tailnet）────┐
                                                     │ bot          (同一份程式碼)│
                                                     │ queue-server (FastAPI)    │
                                                     │   └ SQLite：只存任務資料   │
                                                     │ heartbeat 監控            │
                                                     └───────────▲───────────────┘
                                                                 │ Tailscale（HTTPS + API Token）
                                                                 │ worker 主動拉取 / 回報
                                                     ┌───────────┴───────────────┐
                                                     │ Mac mini                  │
                                                     │ worker（RemoteQueueClient）│
                                                     │ fileserver（同 Phase 1）   │
                                                     │ yt-dlp（住宅 IP）          │
                                                     └───────────────────────────┘
```

### 5.3 與 Phase 1 的差異

| 項目 | Phase 1 | Phase 2 |
|---|---|---|
| `QUEUE_BACKEND` | `sqlite` | Bot 端用 `sqlite`（在 VPS 上）；worker 端用 `remote` |
| Bot 執行位置 | Mac mini | VPS |
| 完成通知 | worker 直接呼叫 Telegram | worker 呼叫 `POST /jobs/{id}/complete`，由 VPS 的 bot 通知使用者 |
| Bot Token 存放位置 | Mac mini | **只存在 VPS**（Mac mini 不需要） |
| 下載連結 | 指向 Mac mini | 同樣指向 Mac mini（Mac mini 睡眠時連結暫時無法開啟，Bot 會提示這一點） |
| 監控 | 無 | worker 每 60 秒送一次 heartbeat；超過 N 分鐘沒收到，Bot 通知「Mac mini 離線」 |

### 5.4 Queue Server API（只綁在 VPS 的 tailnet 介面）

所有請求都必須帶 `Authorization: Bearer <WORKER_API_TOKEN>`。這個 token 只存在 VPS 和 Mac mini 兩處。

| Method | Path | 說明 |
|---|---|---|
| `POST` | `/v1/jobs/claim` | worker 領取一個 `queued` 任務，回傳 Job 或 `204` |
| `POST` | `/v1/jobs/{id}/progress` | 回報進度（百分比） |
| `POST` | `/v1/jobs/{id}/complete` | 回報完成：`file_id`、檔案大小、簽章連結 |
| `POST` | `/v1/jobs/{id}/fail` | 回報失敗：錯誤代碼與訊息（需過濾敏感資訊） |
| `POST` | `/v1/heartbeat` | worker 心跳 |

Queue Server 的設計要求：

- **由 worker 主動拉取，VPS 從不主動連進 Mac mini。**
- 被領取的任務若超過 `LEASE_SECONDS` 都沒有進度回報，就退回 `queued` 狀態，最多重試 `MAX_ATTEMPTS` 次。

### 5.5 Mac mini 定時喚醒

```bash
sudo pmset -a sleep 30                                  # 恢復自動睡眠
sudo pmset repeat wakeorpoweron MTWRFSU 08:00:00        # 每天 08:00 喚醒
# worker 處理完佇列、閒置 N 分鐘後，可以呼叫 `pmset sleepnow`
# （需要另外設定 sudoers 規則只允許這一條指令；預設不開啟）
```

### 5.6 VPS 安全基線

- 只允許 SSH 金鑰登入；關閉密碼登入與 root 登入；最好只允許從 tailnet 連 SSH。
- 啟用 `ufw`：預設拒絕所有連入。Tailscale 透過連出建立連線，因此不需要開放任何連入埠。
- 開啟 `unattended-upgrades` 自動安裝安全更新。
- 服務以非 root 帳號執行。
- 這台機器上只有：Bot Token、`WORKER_API_TOKEN`、任務資料庫。

### 5.7 切換步驟

1. 在 VPS 部署同一份程式碼，設定 `MODE=hybrid-vps`。
2. 在 Mac mini 停止 `mediabot-bot`，worker 改為 `MODE=hybrid-worker`，並設定 `QUEUE_REMOTE_URL`。
3. 遷移：把 Mac mini SQLite 中未完成的任務匯出，再匯入 VPS。
4. 回退：把兩邊的設定改回 `MODE=standalone`，並在 Mac mini 重新啟動 bot。

---

## 6. Phase 3：字幕辨識與翻譯流水線（預留）

本階段的細節另外寫成文件。這裡只先定義介面和選用的技術，確保 Phase 1 預留了擴充點。

### 6.1 流程

```
下載完成的影片
  → ① 用 ffmpeg 抽出音訊（16kHz 單聲道 WAV）
  → ② VAD 偵測語音段落（Silero）；背景音樂多的影片可選擇先用 Demucs 分離人聲
  → ③ ASR 語音辨識（候選：Whisper large-v3 / large-v3-turbo、菲律賓語微調模型、雲端 API）
  → ④ 詞級時間對齊（WhisperX 或模型本身輸出的時間戳）
  → ⑤ 斷句：依語意與時長重新切成適合字幕的句子
  → ⑥ LLM 翻譯成台灣繁體中文（帶上下文視窗與術語表，以 JSON 輸入輸出並保留 id）
  → ⑦ 依中文字數重新調整時間軸（每行 ≤ 16–18 字，每秒 ≤ 7–9 字）
  → ⑧ 輸出 SRT/ASS → 用 ffmpeg 燒錄（libass）或封裝成軟字幕軌
```

### 6.2 技術選擇原則

- ASR 在 Mac mini 原生環境執行，以使用 Metal 或 Apple Neural Engine 加速（whisper.cpp 或 MLX Whisper）。
- 選定模型前，先建立 20–30 段自己影片的人工校正標準答案，用 CER/WER 比較各候選模型。
- 塔加洛語的拼寫變化大，以 CER 作為主要指標。
- 每個步驟的輸入與輸出都存成 JSON 中間檔，放在 `work/{job_id}/`，方便單獨重跑某一步。
- 可參考的開源專案：VideoLingo（整體流程）、WhisperX（詞級時間對齊）、srtforge（翻譯後重新切分字幕）。

### 6.3 Phase 1 預留的介面

```python
# src/mediabot/pipeline/hooks.py
async def on_download_complete(job: Job, file: StoredFile) -> None:
    """Phase 1：不做任何事。Phase 3：若 job.options.subtitle 為 True，建立字幕子任務。"""
```

---

## 7. 模組設計與介面定義

### 7.1 專案目錄結構

```
mediabot/
├── pyproject.toml              # 依賴版本鎖定（使用 uv 或 pip-tools）
├── README.md
├── docs/
│   └── PLAN.md                 # 本文件
├── .env.example                # 只放變數名稱，不放真實的值
├── src/mediabot/
│   ├── __init__.py
│   ├── config.py               # 讀取 .env，以 pydantic-settings 驗證
│   ├── models.py               # Job、StoredFile、JobStatus 等資料模型
│   ├── security/
│   │   ├── urls.py             # validate_url()
│   │   ├── signing.py          # sign_link() / verify_link()
│   │   └── ratelimit.py
│   ├── downloader/
│   │   ├── presets.py          # PRESETS 白名單
│   │   └── runner.py           # 呼叫 yt-dlp Python API
│   ├── queue/
│   │   ├── base.py             # JobQueue Protocol
│   │   ├── sqlite_queue.py     # Phase 1 與 Phase 2（VPS 端）使用
│   │   └── remote_client.py    # Phase 2 worker 端使用
│   ├── worker/
│   │   └── main.py
│   ├── bot/
│   │   ├── main.py
│   │   └── handlers.py
│   ├── fileserver/
│   │   └── app.py
│   ├── queue_server/           # Phase 2
│   │   └── app.py
│   ├── notify/
│   │   ├── base.py             # Notifier Protocol
│   │   ├── telegram.py         # Phase 1
│   │   └── via_queue.py        # Phase 2 worker 端：經由 queue server 轉送通知
│   └── pipeline/
│       └── hooks.py            # Phase 3 擴充點
├── deploy/
│   ├── macos/
│   │   ├── com.mediabot.bot.plist
│   │   ├── com.mediabot.worker.plist
│   │   ├── com.mediabot.fileserver.plist
│   │   ├── com.mediabot.update.plist
│   │   └── install.sh
│   └── vps/
│       ├── mediabot-bot.service
│       ├── mediabot-queue.service
│       └── install.sh
└── tests/
    ├── test_urls.py
    ├── test_signing.py
    ├── test_presets.py
    ├── test_queue.py
    ├── test_fileserver.py
    └── test_bot_auth.py
```

### 7.2 核心介面

```python
# queue/base.py
from typing import Protocol
from mediabot.models import Job, JobResult

class JobQueue(Protocol):
    async def enqueue(self, job: Job) -> int: ...              # 回傳在佇列中的位置
    async def claim(self, worker_id: str) -> Job | None: ...
    async def progress(self, job_id: str, percent: float) -> None: ...
    async def complete(self, job_id: str, result: JobResult) -> None: ...
    async def fail(self, job_id: str, code: str, message: str) -> None: ...
    async def get(self, job_id: str) -> Job | None: ...

# notify/base.py
class Notifier(Protocol):
    async def job_queued(self, job: Job, position: int) -> None: ...
    async def job_done(self, job: Job, link: str) -> None: ...
    async def job_failed(self, job: Job, code: str) -> None: ...
```

**切換原則：** bot 和 worker 只依賴 `JobQueue` 與 `Notifier` 這兩個 Protocol。要用哪個實作，由 `config.MODE` 在啟動時決定（factory），業務邏輯不需要知道目前跑在哪個階段。

### 7.3 網址驗證（S5）

```python
# security/urls.py
from urllib.parse import urlparse, parse_qs
import ipaddress, re

ALLOWED_HOSTS = {"www.youtube.com", "youtube.com", "m.youtube.com", "youtu.be"}
MAX_URL_LEN = 300
VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

class InvalidURL(ValueError): ...

def validate_url(raw: str) -> str:
    """回傳標準化網址 https://www.youtube.com/watch?v=<id>；不合法則丟出 InvalidURL。"""
    raw = raw.strip()
    if len(raw) > MAX_URL_LEN:
        raise InvalidURL("too_long")
    u = urlparse(raw)
    if u.scheme != "https" or u.username or u.password or u.port:
        raise InvalidURL("scheme_or_auth")
    host = (u.hostname or "").lower()
    try:
        ipaddress.ip_address(host)
        raise InvalidURL("ip_host")
    except ValueError:
        pass
    if host not in ALLOWED_HOSTS:
        raise InvalidURL("host_not_allowed")

    if host == "youtu.be":
        vid = u.path.lstrip("/").split("/")[0]
    elif u.path.startswith("/shorts/"):
        vid = u.path.split("/")[2] if len(u.path.split("/")) > 2 else ""
    else:
        vid = parse_qs(u.query).get("v", [""])[0]
    if not VIDEO_ID_RE.match(vid):
        raise InvalidURL("bad_video_id")
    return f"https://www.youtube.com/watch?v={vid}"
```

> 擴充其他網站時，必須在 `ALLOWED_HOSTS` 中明確加入該網域，並為它寫對應的標準化函式與測試，不可用萬用字元放寬限制。

### 7.4 預設方案（S3）

```python
# downloader/presets.py
PRESETS: dict[str, dict] = {
    "video_mp4": {
        "label": "影片 MP4（最高 1080p）",
        "opts": {
            "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080][ext=mp4]/b",
            "merge_output_format": "mp4",
        },
    },
    "audio_m4a": {
        "label": "只要音訊 M4A",
        "opts": {
            "format": "ba[ext=m4a]/ba",
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
        },
    },
    "video_with_subs": {
        "label": "影片 + 原生字幕",
        "opts": {
            "format": "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b",
            "merge_output_format": "mp4",
            "writesubtitles": True,
            "subtitleslangs": ["en", "fil", "tl"],
            "subtitlesformat": "srt/best",
        },
    },
}
```

### 7.5 下載執行（S4、S8、S12）

```python
# downloader/runner.py（重點摘要）
import yt_dlp

BASE_OPTS = {
    "outtmpl": {"default": "%(id)s.%(ext)s"},
    "paths": {"home": DOWNLOAD_DIR, "temp": WORK_DIR},
    "noplaylist": True,
    "max_filesize": cfg.MAX_FILESIZE_BYTES,
    "restrictfilenames": True,
    "windowsfilenames": True,
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "retries": 3,
    "sleep_interval_requests": 1,
    # 嚴禁加入：exec、exec_before_download、cookiesfrombrowser、external_downloader 等
}

def _match_filter(info, *, incomplete):
    if info.get("is_live") or info.get("was_live"):
        return "live_not_supported"
    dur = info.get("duration") or 0
    if dur > cfg.MAX_DURATION_SECONDS:
        return "too_long"
    return None

def run(job: Job, progress_cb) -> JobResult:
    opts = {**BASE_OPTS, **PRESETS[job.preset]["opts"],
            "match_filter": _match_filter,
            "progress_hooks": [progress_cb]}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(job.canonical_url, download=True)
        path = ydl.prepare_filename(info)  # 合併或轉檔後副檔名可能改變，需再檢查一次實際檔案
    return JobResult(...)
```

- worker 同時只執行 `MAX_CONCURRENT_JOBS`（預設 1）個任務。
- 每個任務都在 `asyncio.to_thread` 或獨立的子程序中執行，並設定逾時時間 `JOB_TIMEOUT_SECONDS`。

### 7.6 簽章下載連結（S7）

```python
# security/signing.py
import hmac, hashlib, time, base64

def sign_link(file_id: str, ttl: int) -> str:
    exp = int(time.time()) + ttl
    msg = f"{file_id}:{exp}".encode()
    sig = base64.urlsafe_b64encode(
        hmac.new(cfg.LINK_SECRET.encode(), msg, hashlib.sha256).digest()
    ).decode().rstrip("=")
    return f"{cfg.PUBLIC_BASE_URL}/f/{file_id}?exp={exp}&sig={sig}"

def verify_link(file_id: str, exp: int, sig: str) -> bool:
    if exp < time.time():
        return False
    expected = sign_link_raw(file_id, exp)   # 與 sign_link 相同的計算方式，只回傳 sig
    return hmac.compare_digest(expected, sig)
```

fileserver 的規則：

- 只提供 `GET /f/{file_id}` 與 `GET /healthz` 兩個端點。
- `file_id` 必須是 UUID 格式；用它到資料庫查出絕對路徑後，再確認 `resolved_path.is_relative_to(DOWNLOAD_DIR)`。
- 以 `FileResponse` 串流回傳，並加上 `Content-Disposition: attachment` 與 `X-Content-Type-Options: nosniff` 標頭。
- 關閉 FastAPI 的 `/docs`、`/redoc` 與 `/openapi.json`。

### 7.7 Bot 驗證（S6）

```python
# bot/handlers.py（重點摘要）
async def guard(update) -> bool:
    u, chat = update.effective_user, update.effective_chat
    if not u or chat.type != "private" or u.id not in cfg.ALLOWED_USER_IDS:
        log.warning("unauthorized user_id=%s", getattr(u, "id", None))
        return False            # 不回覆任何訊息
    if not ratelimit.allow(u.id):
        await update.message.reply_text("太頻繁了，請稍後再試")
        return False
    return True
```

Bot 指令：

| 指令 | 功能 |
|---|---|
| （直接傳網址） | 選擇方案後建立任務 |
| `/status` | 查看目前的佇列與進行中的任務 |
| `/recent` | 最近 10 筆完成的任務，可以重新產生連結 |
| `/cancel <id>` | 取消排隊中的任務 |
| `/help` | 使用說明 |

BotFather 設定：

- 關閉 **Allow Groups**。
- 設定 `/setprivacy` 為 Enable。
- 設定指令清單。

---

## 8. 資料模型

### 8.1 SQLite schema

```sql
PRAGMA journal_mode = WAL;

CREATE TABLE jobs (
    id              TEXT PRIMARY KEY,          -- UUID v4
    chat_id         INTEGER NOT NULL,
    user_id         INTEGER NOT NULL,
    canonical_url   TEXT NOT NULL,
    preset          TEXT NOT NULL,
    options_json    TEXT NOT NULL DEFAULT '{}',-- 例如 {"subtitle": false}（Phase 3 使用）
    status          TEXT NOT NULL CHECK (status IN
                    ('queued','running','done','failed','cancelled')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    worker_id       TEXT,
    lease_until     INTEGER,                   -- epoch 秒
    progress        REAL DEFAULT 0,
    error_code      TEXT,
    error_message   TEXT,                      -- 已過濾敏感資訊
    file_id         TEXT,
    created_at      INTEGER NOT NULL,
    updated_at      INTEGER NOT NULL
);
CREATE INDEX idx_jobs_status_created ON jobs(status, created_at);

CREATE TABLE files (                           -- 只存在 Mac mini
    id              TEXT PRIMARY KEY,          -- UUID v4（簽章連結中使用的 file_id）
    job_id          TEXT NOT NULL REFERENCES jobs(id),
    video_id        TEXT NOT NULL,
    title           TEXT,                      -- 只用於顯示，不作為檔名
    rel_path        TEXT NOT NULL,             -- 相對於 DOWNLOAD_DIR 的路徑
    size_bytes      INTEGER NOT NULL,
    sha256          TEXT,
    created_at      INTEGER NOT NULL,
    expires_at      INTEGER                    -- 自動清理的時間
);

CREATE TABLE heartbeats (                      -- Phase 2，存在 VPS
    worker_id       TEXT PRIMARY KEY,
    last_seen       INTEGER NOT NULL
);
```

### 8.2 狀態轉換

```
queued ──claim──▶ running ──complete──▶ done
   ▲                 │
   │   lease 逾時     ├──fail（可重試，attempts < MAX）──▶ queued
   └─────────────────┤
                     └──fail（不可重試或已達上限）──▶ failed
queued ──/cancel──▶ cancelled
```

不可重試的錯誤代碼：`too_long`、`live_not_supported`、`host_not_allowed`、`file_too_large`、`unavailable`。

---

## 9. 設定檔與模式切換

### 9.1 `.env.example`

```dotenv
# ===== 模式 =====
# standalone     ：Phase 1，Mac mini 執行全部服務
# hybrid-vps     ：Phase 2，VPS 執行 bot 與 queue-server
# hybrid-worker  ：Phase 2，Mac mini 執行 worker 與 fileserver
MODE=standalone

# ===== Telegram（standalone 與 hybrid-vps 才需要）=====
TG_BOT_TOKEN=
ALLOWED_USER_IDS=123456789

# ===== 路徑 =====
VAULT_DIR=/Users/mediabot/MediaVault

# ===== 檔案伺服器 =====
FILESERVER_BIND=127.0.0.1:8080
PUBLIC_BASE_URL=https://mac-mini.your-tailnet.ts.net
LINK_SECRET=                     # 用 `python -c "import secrets;print(secrets.token_urlsafe(48))"` 產生
LINK_TTL_SECONDS=86400

# ===== 資源上限 =====
MAX_FILESIZE_BYTES=4294967296    # 4 GB
MAX_DURATION_SECONDS=10800       # 3 小時
MAX_CONCURRENT_JOBS=1
JOB_TIMEOUT_SECONDS=7200
RATE_LIMIT_PER_HOUR=30
FILE_RETENTION_DAYS=14

# ===== Phase 2 =====
QUEUE_BACKEND=sqlite             # sqlite | remote
QUEUE_REMOTE_URL=                # 例如 https://vps-name.your-tailnet.ts.net
WORKER_API_TOKEN=
WORKER_ID=mac-mini
LEASE_SECONDS=900
MAX_ATTEMPTS=3
HEARTBEAT_ALERT_MINUTES=30
```

### 9.2 各模式啟動的程序

| MODE | bot | queue-server | worker | fileserver | Notifier | JobQueue |
|---|---|---|---|---|---|---|
| `standalone` | ✅ | ❌ | ✅ | ✅ | `TelegramNotifier` | `SqliteQueue` |
| `hybrid-vps` | ✅ | ✅ | ❌ | ❌ | `TelegramNotifier` | `SqliteQueue` |
| `hybrid-worker` | ❌ | ❌ | ✅ | ✅ | `ViaQueueNotifier` | `RemoteQueueClient` |

`config.py` 啟動時要驗證：該模式需要的變數都已設定；`hybrid-worker` 模式下**不可**設定 `TG_BOT_TOKEN`（確保 Mac mini 上沒有 Bot Token）。

---

## 10. 部署與維運

### 10.1 macOS LaunchDaemon 範例

```xml
<!-- /Library/LaunchDaemons/com.mediabot.worker.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>             <string>com.mediabot.worker</string>
  <key>UserName</key>          <string>mediabot</string>
  <key>WorkingDirectory</key>  <string>/Users/mediabot/app</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/mediabot/app/.venv/bin/python</string>
    <string>-m</string>
    <string>mediabot.worker.main</string>
  </array>
  <key>EnvironmentVariables</key>
  <dict>
    <key>MEDIABOT_ENV_FILE</key> <string>/Users/mediabot/app/.env</string>
    <key>PATH</key>              <string>/opt/homebrew/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key>         <true/>
  <key>KeepAlive</key>         <true/>
  <key>ThrottleInterval</key>  <integer>30</integer>
  <key>StandardOutPath</key>   <string>/Users/mediabot/MediaVault/logs/worker.out.log</string>
  <key>StandardErrorPath</key> <string>/Users/mediabot/MediaVault/logs/worker.err.log</string>
</dict>
</plist>
```

```bash
sudo launchctl bootstrap system /Library/LaunchDaemons/com.mediabot.worker.plist
sudo launchctl kickstart -k system/com.mediabot.worker     # 重啟
sudo launchctl bootout system/com.mediabot.worker          # 停止
```

`com.mediabot.update.plist`：使用 `StartCalendarInterval`，每週日 04:00 執行以下指令，再重啟 worker：

```bash
.venv/bin/pip install -U yt-dlp
```

### 10.2 檔案與權限

```bash
chmod 600 /Users/mediabot/app/.env
chown mediabot:staff /Users/mediabot/app/.env
chmod 700 /Users/mediabot/MediaVault
```

### 10.3 日誌

- 使用 Python `logging` 搭配 `RotatingFileHandler`（10 MB × 5 份）。
- **過濾敏感資訊：** 設定一個 log filter，把符合 Bot Token 格式（`\d+:[A-Za-z0-9_-]{35}`）、`sig=`、`Authorization` 的字串替換成 `***`。
- 不記錄完整的 yt-dlp 例外堆疊中的 HTTP 標頭。

### 10.4 自動清理

worker 每小時執行一次：刪除 `files.expires_at < now` 的檔案和紀錄，以及 `work/` 中超過 24 小時的暫存檔。

### 10.5 備份

- 資料庫：每天用 `sqlite3 .backup` 備份到 `db/backup/`，保留 7 份。
- 影片：不備份，視為可以重新下載的快取。

### 10.6 故障排查速查

| 症狀 | 檢查方式 |
|---|---|
| Bot 沒反應 | `launchctl print system/com.mediabot.bot`；查看 `logs/bot.err.log`；確認網路連線 |
| 下載出現 `Sign in to confirm…` | 先更新 yt-dlp；暫停下載一段時間；**不要**自行加入 cookie（S11） |
| 連結打不開 | 確認裝置已連上 Tailscale；在 Mac mini 執行 `tailscale serve status`；確認連結未過期 |
| 停電後服務沒啟動 | FileVault 需要有人登入解鎖（見第 14 節） |

---

## 11. 測試計畫

### 11.1 單元測試（pytest，必須全數通過才能合併）

**`test_urls.py`**

- 合法網址：`watch?v=`、`youtu.be/`、`/shorts/`、`m.youtube.com`。
- 必須拒絕的網址：
  - `http://` 開頭
  - `https://evil.com/?v=youtube.com`
  - `https://youtube.com.evil.com/`
  - `https://user:pass@youtube.com/`
  - `https://127.0.0.1/`
  - `https://[::1]/`
  - `https://youtube.com:8443/`
  - 超長網址
  - 含換行或 `;` 的字串
  - `file:///etc/passwd`
  - `--exec=whoami`

**`test_presets.py`**

- 不存在的方案名稱必須丟出例外。
- 所有方案的 opts 都不可包含 `exec`、`exec_cmd`、`cookiesfrombrowser`、`external_downloader` 等禁止的鍵，`postprocessors` 中也不可出現 `key` 為 `Exec` / `ExecAfterDownload` 的項目（`--exec` 在 Python API 中的形式）。

**`test_signing.py`**

- 正確簽章可通過驗證；竄改 file_id、exp 或 sig 都會失敗；過期的連結會失敗。

**`test_fileserver.py`**

- 非 UUID 格式的 file_id 回傳 404。
- 路徑穿越（`../`）回傳 404。
- 簽章錯誤回傳 403。
- `/docs` 回傳 404。

**`test_bot_auth.py`**

- 非白名單使用者、群組訊息都不會得到回覆，也不會建立任務。

**`test_queue.py`**

- 狀態轉換正確；lease 逾時後任務退回 `queued`；重試達到上限後轉為 `failed`。

### 11.2 整合測試（手動，或用 `pytest -m integration`）

- 用一部短的、創用 CC 授權的公開影片，測試完整流程：傳網址 → 下載 → 收到連結 → 下載成功。
- 測試超過長度上限的影片，應回覆 `too_long`。

### 11.3 安全檢查清單（每次發版前執行）

- [ ] `rg "shell=True|os\.system|cookiesfrombrowser|exec" src/` 無結果。
- [ ] `pip-audit` 沒有高風險漏洞。
- [ ] 從 tailnet 外部（例如關閉 Tailscale 的手機）無法連到 fileserver。
- [ ] 用另一個 Telegram 帳號傳訊息給 Bot，Bot 沒有任何回應。
- [ ] `.env` 權限為 600，且不在 git 中（`.gitignore` 已包含 `.env`）。

---

## 12. AI 協作規範

給 AI 協作者（例如 Claude、Codex 等）的工作規則：

1. **第 2 節安全守則優先於任何功能需求。** 若某項需求必須違反守則，停止實作，並向擁有者說明取捨。
2. **不可新增**以下內容：
   - 讓使用者傳入任意 yt-dlp 參數或指令的功能；
   - 公開的對外連入埠口；
   - 讀取瀏覽器 cookie 的功能。
3. 新增網站支援時，必須同時提交 `ALLOWED_HOSTS` 的修改、對應的標準化函式，以及正向與反向的測試案例。
4. 業務邏輯只依賴 `JobQueue` 和 `Notifier` 這兩個 Protocol，不可在 bot 或 worker 中寫死 SQLite 或 Telegram 的呼叫。
5. 每個 PR 都必須包含測試，並通過 `ruff`、`mypy --strict`（至少 `security/` 和 `downloader/` 兩個模組）與 `pytest`。
6. 機密資訊只透過 `config.py` 取得。程式碼、測試、範例檔中不可出現真實的 token。
7. 依賴套件的新增或升級需在 PR 中說明理由。優先使用維護活躍、下載量大的套件。
8. 修改架構時，請同步更新本文件，並在文件末尾的變更紀錄中加一行。
9. 遇到不確定的平台限制（例如 API 上限、macOS 行為），先查證官方文件，並在程式碼註解中記錄來源與查證日期。

---

## 13. 里程碑與任務清單

### Phase 1：Mac mini 單機

- [ ] **M0.5 專案骨架**：pyproject、工具鏈、`scripts/check_forbidden.py`、CI、AI 規則對齊（`docs/specs/2026-11-22-m0.5-project-skeleton.md`）
- [ ] **M0 環境建置**
  - [ ] Mac mini：設定 pmset、防火牆，建立專用帳號 `mediabot`
  - [ ] 安裝 Homebrew 版的 python、ffmpeg、tailscale；所有裝置加入 tailnet；設定 ACL
  - [ ] 在 BotFather 建立 Bot，關閉 Allow Groups
- [ ] **M1 下載核心**：`config.py`、`security/urls.py`、`downloader/`，並附單元測試
  - 完成標準：在 CLI 執行 `python -m mediabot.downloader <url> video_mp4` 可以成功下載
- [ ] **M2 佇列與 Worker**：`queue/sqlite_queue.py`、`worker/main.py`，包含 lease、重試與清理
- [ ] **M3 Telegram Bot**：驗證、頻率限制、InlineKeyboard 選方案、`/status`、`/recent`、`/cancel`
- [ ] **M4 檔案伺服器**：簽章連結、`tailscale serve`、完成通知
- [ ] **M5 維運強化**：launchd plist、自動更新、日誌敏感資訊過濾、備份、完成安全檢查清單
  - 完成標準：連續穩定運作 7 天

### Phase 2：混合架構

- [ ] **M6** `queue_server/`（FastAPI）與 `queue/remote_client.py`、`notify/via_queue.py`
- [ ] **M7** VPS 部署：安全基線、systemd、加入 tailnet、heartbeat 離線告警
- [ ] **M8** 切換演練：standalone → hybrid → standalone（回退）都能順利完成

### Phase 3：字幕流水線

- [ ] **M9** 建立 ASR 評估資料集（20–30 段，含人工校正），比較候選模型
- [ ] **M10** 實作流程：音訊抽取 → VAD → ASR → 時間對齊 → 斷句
- [ ] **M11** LLM 翻譯：上下文視窗、術語表、JSON 格式輸入輸出
- [ ] **M12** 重新調整時間軸、輸出 ASS、燒錄或封裝軟字幕；Bot 新增「送去翻譯字幕」按鈕

---

## 14. 已知限制與待確認事項

| 項目 | 說明 | 對策 |
|---|---|---|
| FileVault 與停電重開機 | 開啟 FileVault 時無法自動登入，停電重開後需要有人輸入密碼解鎖磁碟，服務才會啟動 | 加裝 UPS；Phase 2 的 heartbeat 會在離線時發出告警。**待確認**：目前的 macOS 版本是否支援透過 SSH 遠端解鎖 FileVault |
| Mac mini 睡眠時下載連結失效 | Phase 2 中，Mac mini 睡眠時無法下載檔案 | Bot 回覆時註明；之後可以考慮在醒著時同步到 iCloud 或 NAS |
| YouTube 偵測規則變動 | 下載可能突然失敗 | 每週自動更新 yt-dlp；降低請求頻率；不使用反封鎖手段 |
| Telegram 對話沒有端對端加密 | Telegram 伺服器看得到傳送的網址 | 只傳公開影片網址；檔案一律經由 Tailscale 傳輸，不經過 Telegram |
| Telegram Bot 傳檔上限 50 MB | 官方 Bot API 的限制 | 影片一律改傳連結；只有小檔案（音訊、字幕）才直接傳送 |
| 免費 VPS 方案變動 | 例如 Oracle 在 2026 年縮減了 Always Free 的 ARM 額度 | Phase 2 的 VPS 端只需要極少資源，GCP e2-micro 等級就夠用；保持部署腳本可以移植到其他業者 |

---

## 變更紀錄

| 日期 | 版本 | 內容 |
|---|---|---|
| 2026-11-22 | v0.1 | 初版：確定 Phase 1（Mac mini 不休眠）為主要方案，Phase 2（VPS 混合）為進階方案，Phase 3 預留字幕流水線 |
| 2026-11-22 | v0.2 | 新增 `docs/DEVELOPMENT.md` 開發流程；§13 插入 M0.5；mypy 改為全專案 strict（原 §12-5 為至少 security/、downloader/）；§11.3 的 `rg` 掃描改由 `scripts/check_forbidden.py` 執行；ADR-0001（yt-dlp 經 lockfile 更新，取代 §10.1 的 `pip install -U`）、ADR-0002（SQLite 使用標準庫與 `PRAGMA user_version`） |
