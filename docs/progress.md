# 進度紀錄

<!-- 由 /progress 維護，作為跨 session 的工作記憶。保持在 40 行內；舊內容移到 progress-archive.md -->

## 進行中
- 任務：M1 下載核心（規格：`docs/specs/2026-11-22-m1-download-core.md`，分支 `feat/m1-download-core`，從 `feat/m0.5-project-skeleton` 開出，PR #1 merge 後 rebase 到 `main`）
  - [x] 規格確認；步驟 1–6、8 完成（145 tests），Q1–Q5 本機通過，已在本機 commit、尚未 push
  - [ ] 步驟 7：擁有者提供影片網址 → `MEDIABOT_IT_URL=<url> uv run pytest -m integration`，並手動跑 CLI，結果記在規格
  - [ ] `/review` → push → 開 PR（PR #1 merge 後 rebase 到 `main`）
- M0.5 收尾（PR #1，CI checks ×2 與 pip-audit 已通過）
  - [ ] 擁有者修正 `.claude/settings.json` deny 清單（見已知問題）後推上 PR #1
  - [ ] 擁有者 merge PR #1

## 仍有效的決策
- 2026-11-22：DEVELOPMENT.md §12 全部採建議方案（M0.5 插入、sqlite3 標準庫、user_version、yt-dlp 經 lock 更新、測試用 Bot）
- 2026-11-22：mypy 全專案 strict；ruff 排除 `.claude/`、`docs/`，忽略 RUF001–003
- 2026-11-22：`.env*` 保護改為 deny 明列檔名（deny 優先於 allow，無法用 allow 例外放行 `.env.example`）
- 2026-11-22：M1 依賴採 `yt-dlp[default,deno]` + pydantic-settings（ADR-0003）；M1 不做 `video_with_subs`；`config.py` 只放 M1 欄位；`runner.run()` 收 url + preset，`Job` 留到 M2

## 已知問題 / 待辦
- `.claude/settings.json` deny：`Read(./.env.develoment)` 拼錯（缺 `p`）；尚未涵蓋 `.env.test`、`.env.staging`、`.env.prod`
- GitHub Claude review job 失敗：repo 未安裝 Claude Code GitHub App（https://github.com/apps/claude），且未設定 secret `CLAUDE_CODE_OAUTH_TOKEN`
- M1 整合測試需要擁有者提供短的創用 CC 影片網址（環境變數 `MEDIABOT_IT_URL`）

## 已完成
- 2026-11-22：規劃文件（PLAN v0.2、DEVELOPMENT.md）、初始 commit 推上 main
