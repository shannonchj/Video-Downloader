# MediaBot

個人自架工具：透過 Telegram Bot 傳送影片網址 → 在 Mac mini 下載 → 經 Tailscale 取得私人下載連結；後續擴充字幕辨識、翻譯成台灣繁體中文與燒錄輸出。

僅供擁有者本人使用，只下載有權使用的內容。

## 文件

- [`docs/PLAN.md`](docs/PLAN.md)：專案規劃與**安全守則**（修改程式前必讀 §2、§12）
- [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md)：開發流程與品質閘門
- [`docs/architecture.md`](docs/architecture.md)：目前已實作的架構
- [`docs/decisions/`](docs/decisions/)：架構決策紀錄（ADR）

## 開發

需要 [uv](https://docs.astral.sh/uv/) 與 Python 3.12。

```bash
uv sync                                          # 安裝依賴
uv run ruff format --check . && uv run ruff check .
uv run mypy
uv run pytest -x -q
uv run python scripts/check_forbidden.py         # 危險寫法掃描
uv run pip-audit                                 # 依賴漏洞掃描
```

設定檔：複製 `.env.example` 為 `.env` 並填入值（`.env` 不進 git）。
