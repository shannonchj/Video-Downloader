# ADR-0002：SQLite 使用標準庫 sqlite3，schema 以 PRAGMA user_version 管理

- 狀態：已採用
- 日期：2026-11-22

## 背景
PLAN 使用 SQLite（WAL 模式）作為佇列與檔案紀錄。專案範本的 CLAUDE.md 預設 SQLAlchemy + Alembic + PostgreSQL，與 PLAN 不符。bot、worker、fileserver 都是 async 程式，需要決定 async 存取方式與 schema 變更的管理方式。

## 考慮過的選項
1. `aiosqlite`：原生 async API / 多一個依賴，而且它內部本來就是用執行緒包裝 `sqlite3`。
2. 標準庫 `sqlite3` + `asyncio.to_thread`：零依賴、行為透明 / 需要自己封裝連線與交易。
3. SQLAlchemy + Alembic：功能完整 / 對三張表的規模來說太重，依賴多。

Schema 版本管理：
- A. Alembic：需要 SQLAlchemy。
- B. `PRAGMA user_version` + 依序執行的 `.sql` 檔：零依賴，對 SQLite 來說足夠。

## 決策
採用選項 2 + B。
- 所有資料庫存取都集中在 `queue/sqlite_queue.py` 與檔案紀錄的存取層，以 `asyncio.to_thread` 呼叫同步的 `sqlite3`。
- Migration 放在 `src/mediabot/db/migrations/NNN_<slug>.sql`。啟動時依序套用編號大於 `user_version` 的檔案，每個檔案在同一個交易中執行並更新 `user_version`。
- 已存在的 migration 檔不可修改，只能新增。
- 時間一律存 epoch 秒（UTC，INTEGER），與 PLAN §8.1 一致。

## 影響
- CLAUDE.md 的資料庫規則依本決策改寫（M0.5）。
- M2 規格需定義連線管理方式（每個執行緒一個連線、`busy_timeout`、WAL）與 migration runner 的測試。
