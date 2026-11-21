# 架構說明

<!-- 「已實作」的架構現況；藍圖見 docs/PLAN.md。每個里程碑合併時同步更新 -->

## 系統概觀
目前完成到 M0.5（專案骨架），尚未有執行期功能。目標架構見 `docs/PLAN.md` §4（Phase 1）。

## 模組與職責
| 模組 | 職責 | 備註 |
|---|---|---|
| `src/mediabot/__init__.py` | 套件根目錄，提供 `__version__` | 子套件在各自的里程碑建立 |
| `scripts/check_forbidden.py` | 以 `ast` 掃描 PLAN S3/S4/S11 禁止的寫法（Q4） | 只用標準庫；不提供忽略註解 |

## 資料模型
尚未實作（M2，見 ADR-0002）。

## 外部依賴
- 執行期：無。
- 開發：pytest、pytest-asyncio、httpx、ruff、mypy、pip-audit（版本見 `uv.lock`）。

## 部署與環境
- 開發：Windows 11 + uv 0.13.6 + Python 3.12。
- CI：GitHub Actions `ci.yml`（Ubuntu + Windows，Q1–Q4）、`audit.yml`（pip-audit，每週與依賴變更時）。
- 正式環境：尚未部署（Mac mini，M0 / M5）。

## 已知限制與技術債
- `check_forbidden.py` 無法偵測以下寫法，由 review 把關：動態組成的鍵（`opts["ex" + "ec"]`）、`getattr(os, "system")`、`__import__("os")`、先存進變數的指令字串、`**{"shell": True}` 展開。
- `Exec` postprocessor 的鍵名尚未對照 yt-dlp 原始碼（M1 安裝 yt-dlp 後核對）。
