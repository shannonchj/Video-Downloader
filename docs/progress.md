# 進度紀錄

<!-- 由 /progress 維護，作為跨 session 的工作記憶。保持在 40 行內；舊內容移到 progress-archive.md -->

## 進行中
- 任務：M0.5 專案骨架（規格：`docs/specs/2026-11-22-m0.5-project-skeleton.md`，分支 `feat/m0.5-project-skeleton`，PR #1）
  - [x] 實作 7 步、本機 `/review` 修正、Q1–Q5 本機通過
  - [x] PR #1 CI：checks（Ubuntu、Windows）與 pip-audit 通過
  - [ ] 本次 progress / 規格勾選尚未 commit，需推上 PR #1
  - [ ] 擁有者修正 `.claude/settings.json` deny 清單（見已知問題）後推上 PR #1
  - [ ] 擁有者 merge PR #1 → 下一步：`/plan-feature` M1 下載核心（PLAN §7.3–7.5、§13）

## 仍有效的決策
- 2026-11-22：DEVELOPMENT.md §12 全部採建議方案（M0.5 插入、sqlite3 標準庫、user_version、yt-dlp 經 lock 更新、測試用 Bot）
- 2026-11-22：mypy 全專案 strict；ruff 排除 `.claude/`、`docs/`，忽略 RUF001–003
- 2026-11-22：`.env*` 保護改為 deny 明列檔名（deny 優先於 allow，無法用 allow 例外放行 `.env.example`）

## 已知問題 / 待辦
- `.claude/settings.json` deny：`Read(./.env.develoment)` 拼錯（缺 `p`）；尚未涵蓋 `.env.test`、`.env.staging`、`.env.prod`
- GitHub Claude review job 失敗：repo 未安裝 Claude Code GitHub App（https://github.com/apps/claude），且未設定 secret `CLAUDE_CODE_OAUTH_TOKEN`
- M1：對照 `yt_dlp/postprocessor/exec.py` 核對 `Exec` / `ExecAfterDownload` / `exec_cmd`（`scripts/check_forbidden.py` 的 TODO）
- M1 開始前修正 PLAN 的 P1–P6（DEVELOPMENT.md §10）

## 已完成
- 2026-11-22：規劃文件（PLAN v0.2、DEVELOPMENT.md）、初始 commit 推上 main
