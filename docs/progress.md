# 進度紀錄

<!-- 由 /progress 維護，作為跨 session 的工作記憶。保持在 40 行內；舊內容移到 progress-archive.md -->

## 進行中
- 任務：M0.5 專案骨架（規格：`docs/specs/2026-11-22-m0.5-project-skeleton.md`，分支 `feat/m0.5-project-skeleton`）
  - [x] pyproject / 工具鏈 / smoke test、`check_forbidden.py` + 測試、CI 檔、CLAUDE.md / settings.json / REVIEW.md 對齊、ADR-0001/0002
  - [x] `/review` 的 1 個 Important + 5 個 Nit 已修正（65 tests）；新增 `.gitattributes`（`eol=lf`）並 renormalize
  - [x] `.env.example`（變數與 PLAN §9.1 一致，機密欄位皆空）
  - [ ] 擁有者 `/ship` → 確認 PR 上 CI（Ubuntu + Windows）與 audit 通過

## 仍有效的決策
- 2026-11-22：DEVELOPMENT.md §12 全部採建議方案（M0.5 插入、sqlite3 標準庫、user_version、yt-dlp 經 lock 更新、測試用 Bot）
- 2026-11-22：mypy 全專案 strict；ruff 排除 `.claude/`、`docs/`，忽略 RUF001–003

## 已知問題 / 待辦
- M1：對照 `yt_dlp/postprocessor/exec.py` 核對 `Exec` / `ExecAfterDownload` / `exec_cmd`（`scripts/check_forbidden.py` 的 TODO）
- M1 開始前修正 PLAN §10 的 P1–P6（DEVELOPMENT.md §10）

## 已完成
- 2026-11-22：規劃文件（PLAN v0.2、DEVELOPMENT.md）、初始 commit 推上 main
