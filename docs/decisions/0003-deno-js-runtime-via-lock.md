# ADR-0003：YouTube 解析所需的 JS runtime 使用 uv 鎖定的 deno

- 狀態：已採用
- 日期：2026-11-22

## 背景
yt-dlp 2026.10.26 解析 YouTube 時需要 JavaScript runtime（預設 `js_runtimes={"deno": {}}`），也需要 `yt-dlp-ejs` 提供的腳本；只安裝 yt-dlp 本體可能拿不到可下載的格式。yt-dlp 也提供 `remote_components`，可以在執行時從 npm 或 GitHub 抓取這些腳本。

## 考慮過的選項
1. `yt-dlp[default,deno]`：deno 執行檔與 yt-dlp-ejs 都由 `uv.lock` 鎖定，開發機、CI、Mac mini 版本一致，經 ADR-0001 的流程更新 / 多 9 個套件，deno wheel 約 40 MB。
2. `yt-dlp[default]` + 系統安裝 deno（Homebrew 等）：套件較少 / deno 版本不受 lock 管理，各環境可能不一致，launchd 的 PATH 也要另外設定。
3. 啟用 `remote_components`：不必安裝 yt-dlp-ejs / 執行期從網路下載程式碼，版本不可追溯，違反 S13。

## 決策
採用選項 1。runner 以 `deno.find_deno_bin()` 取得 venv 內的 deno 路徑，明確設定 `js_runtimes`，不依賴 PATH。

## 影響
- **不可啟用 `remote_components`。**
- deno 與 yt-dlp-ejs 的更新與 yt-dlp 相同，走 ADR-0001（升級 lock → PR → `uv sync --frozen`）。
- pip-audit 的檢查範圍包含這些套件。
