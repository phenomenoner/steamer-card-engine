# Live Monitor Sidecar（唯讀監控側車）

本文件定義 `steamer-card-engine` 內的 dashboard / live monitor sidecar 邊界。它是公開文件，只描述可公開的產品架構與安全姿態；部署主機、雲端帳號、內部路徑、私有 receipt 與交易帳號資訊不屬於本文件。

## 定位

Live Monitor Sidecar 是 `steamer-card-engine` 專案內的**唯讀監控側車**，用來把 replay / live-sim / bounded live 產生的 runtime artifacts 轉成可瀏覽的 dashboard 與 API。

它不是交易主引擎，也不是 broker control plane。

```text
steamer-card-engine runtime outputs
  -> dashboard runtime store sidecar
      -> FastAPI / React live monitor
```

## 權限邊界

Sidecar 可以：

- 讀取 runtime 輸出的 tick / event / decision / order artifacts。
- 建立或更新本機 SQLite runtime store。
- 提供唯讀 API 與前端 dashboard。
- 將同一日期、同一 symbol 的 runtime ticks 聚合成 bars。
- 提供 decision aggregate 摘要，協助操作者理解策略為什麼沒有進場。

Sidecar 不可以：

- 下單。
- 改寫 card / deck / strategy policy。
- 持有 broker authority。
- 讀取或暴露 credentials、帳號、私有 receipt、部署主機內部資訊。
- 用 mounted observer candles 假裝成某個 runtime date/symbol 的精確行情。

## Runtime store

Runtime store 是 sidecar 的本機 SQLite 索引層。它的目的不是取代原始 artifacts，而是讓 dashboard 可以快速查詢：

- runtime dates catalog
- symbol bars
- tick provenance
- decision aggregates
- order summaries

目前 schema 以 `steamer-dashboard-runtime-store-v9` 為版本名。重要設計：

- tick provenance 透過 `source_files` 正規化來源檔案。
- tick 使用 `tick_fingerprint` 去重，避免 `event-log.jsonl` 與 `ticks.jsonl` 重複計數。
- runtime date catalog 會合併 DB catalog 與本地 artifacts / watchlist / fixture evidence；它是 catalog-aware，不是 catalog-only。
- freshness 以目標日期的 `runs.updated_at` 判斷，不以整個 DB 檔案 mtime 判斷。

## Import CLI

Runtime store 由 CLI 維護：

```bash
python -m steamer_card_engine.dashboard.runtime_store_cli \
  --db <runtime-store.sqlite> \
  --root <runtime-artifacts-root> \
  --latest 3 \
  --receipt <import-receipt.json>
```

重要參數：

- `--db`：SQLite runtime store 路徑。
- `--root`：runtime artifacts root。
- `--date YYYY-MM-DD`：指定匯入日期，可重複。
- `--latest N`：匯入最新 N 個可發現的 runtime dates。
- `--receipt`：輸出 machine-readable import receipt。

優先序：

- 明確 `--date` 會覆蓋 `--latest`。
- 未提供 `--date` 且 `--latest 0` 時，會使用 discovery 預設行為。

## API surface

Sidecar API 是唯讀 surface。主要 runtime endpoints：

```text
GET /api/runtime/dates
GET /api/runtime/dates/{date}/symbols/{symbol}/bars?timeframe=1m
GET /api/runtime/dates/{date}/decision-aggregates?symbol={symbol}
```

API 回傳的 `source_kind` 用來揭露資料來源，例如：

- `runtime-store-sqlite-catalog+local-runs+s3-runtime-archive-cache+fixture-compare-index`
- `runtime-store-sqlite-ticks`
- `runtime-ticks-jsonl`
- `runtime-event-log-market-tick`
- `runtime-store-sqlite-decision-aggregates`
- `unavailable`

## UI truth rule

Dashboard 選定 runtime date/symbol 時，只能使用該 date/symbol 的 runtime bars。

如果沒有精確 runtime bars：

- chart 應顯示明確 empty state。
- 不得 fallback 到 mounted observer candles，避免把其他日期或 session 的價格誤顯為 runtime truth。
- 若 mounted observer session 存在，右側 execution state 可以繼續顯示，但 chart truth 必須保持分離。

## Decision aggregates

Decision aggregates 將 raw decision reasons 收斂為：

- `reason_code`：第一個 `:` 前的穩定 bucket。
- `reason_sample`：代表性的原始 reason 文本。

這讓 dashboard 可以呈現「為何沒有進場」的趨勢，而不是被每個數值變化切成大量碎片 bucket。

## 部署姿態

常見部署會使用一個 dashboard service 加上一個 import timer，例如：

- `steamer-observer-dashboard.service`
- `steamer-dashboard-runtime-store-import.service`
- `steamer-dashboard-runtime-store-import.timer`

這些名稱是建議拓撲，不是交易權限。它們只應該操作 dashboard/runtime-store sidecar，不應該變成 broker execution authority。

## Public-safety notes

公開文件與 commit 不應包含：

- 真實主機 IP、雲端帳號、bucket、instance id。
- 私有部署路徑與操作者機器路徑。
- broker credentials、帳號、憑證路徑。
- raw private receipts 或未脫敏交易資料。

公開文件可以描述：

- sidecar 邊界。
- CLI / API contract。
- schema concept。
- safety invariant。
- 測試與行為規則。
