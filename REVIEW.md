# Review instructions

只放 PR review 專用規則；專案慣例以 `CLAUDE.md` 為準，這裡不重複。review 留言用繁體中文，程式碼與識別名稱保留英文。
本檔同時供本機 `/review`（code-reviewer subagent）與 GitHub 上的 Claude review 使用。

## What Important means here

Important 只用在會造成錯誤結果、資料遺失、程序崩潰或安全問題的情況：

- 邏輯錯誤、邊界條件處理錯誤，會產生錯誤結果
- 資料被覆蓋或遺失；例外被靜默吞掉
- 資源沒有釋放、競態條件
- 注入（SQL / 指令）、權限檢查缺漏
- 機密寫死在程式碼或寫進 log
- 不安全的 migration（會遺失資料、修改既有 migration）
- **違反 `docs/PLAN.md` §2 安全守則 S1–S14 任一條**，例如：使用者輸入流入 yt-dlp opts、`shell=True`、網址未經 `validate_url()`、服務綁定非 `127.0.0.1`、檔名使用影片標題、fileserver 使用 URL 中的路徑、Bot 回應白名單外的使用者
- bot 或 worker 繞過 `JobQueue` / `Notifier` Protocol，直接呼叫 SQLite 或 Telegram（PLAN §12-4）
- `scripts/check_forbidden.py` 的規則被放寬或刪除，卻沒有對應的規格變更

命名、風格、重構建議最多是 Nit。

## Cap the nits

每次 review 最多 5 個 Nit。

## Do not report

- 格式與 import 排序（formatter / linter 處理）
- lockfile（`uv.lock`）
- `docs/PLAN.md` 中的示意程式碼（以 `docs/specs/` 與實際程式碼為準）

## Always check

- 新邏輯有對應測試，且測試真的驗證行為
- 改了規格、測試流程或架構時，有同步更新 `docs/`
- 沒有用 `print` 取代 logging；沒有新增未說明的依賴
- 沒有把機密、產生的資料或大型二進位檔加進 git
