# ADR-0001：yt-dlp 透過 lockfile 更新，正式環境只安裝鎖定版本

- 狀態：已採用
- 日期：2026-11-22

## 背景
PLAN S13 要求依賴鎖定版本，但 PLAN §10.1 的 `mediabot-update` 排程在 Mac mini 上直接執行 `pip install -U yt-dlp`。這樣正式環境的版本會與 `uv.lock` 不一致，而且新版本沒有經過測試就上線。另一方面，YouTube 改版時，yt-dlp 必須能盡快更新，否則下載會全部失敗。

## 考慮過的選項
1. 維持 PLAN 做法，正式環境直接升級：更新最快 / 版本無法追溯、未經測試、違反 S13。
2. 開發端升級 lock → PR → 正式環境 `uv sync --frozen`：版本可追溯、有測試把關 / 多一道 PR 流程，更新會延遲數小時到一天。

## 決策
採用選項 2。
- 開發端：每週或下載開始失敗時執行 `uv lock --upgrade-package yt-dlp`，跑完測試後走一般 PR 流程。
- Mac mini：`mediabot-update` 改為 `git pull` + `uv sync --frozen` + 重啟服務。
- 緊急情況允許在 Mac mini 上手動升級，但事後必須補一個 PR，讓 `uv.lock` 與正式環境一致。

## 影響
- M5 的 `com.mediabot.update.plist` 與 `install.sh` 依本決策實作，PLAN §10.1 需同步修改。
- Mac mini 需要能讀取 git repo（使用 deploy key 或 HTTPS 唯讀 token），M5 規格中再決定方式。
