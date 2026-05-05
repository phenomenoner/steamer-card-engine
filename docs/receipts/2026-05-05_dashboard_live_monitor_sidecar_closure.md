# 2026-05-05 — Dashboard / Live Monitor Sidecar Closure

## 結論

本階段將 dashboard / live monitor 明確收斂為 `steamer-card-engine` 專案內的**唯讀 sidecar**：它讀取 runtime artifacts、維護本機 runtime store，並提供 FastAPI / React dashboard；它不屬於交易主引擎，不持有 broker authority，也不改寫策略或風控政策。

## 已落地的公開產品能力

- `steamer_card_engine.dashboard.*` 成為 read-only monitor sidecar surface。
- Runtime bars 只接受精確 date/symbol 的 runtime artifacts，不用 mounted observer candles 假裝成 runtime chart truth。
- SQLite runtime store 支援：
  - runtime date catalog；
  - tick provenance；
  - duplicate tick dedupe；
  - per-date freshness；
  - decision aggregate reason-code buckets。
- `runtime_store_cli` 支援：
  - explicit `--date`；
  - discovered `--latest N`；
  - machine-readable receipt。
- Dashboard API 新增 decision aggregates read path。

## 安全邊界

Sidecar 可以讀 runtime artifacts 與輸出 dashboard/API。

Sidecar 不可以：

- 下單；
- 持有 broker credentials 或交易權限；
- 改寫 card / deck / strategy policy；
- 將私有部署主機、雲端帳號、內部路徑、私有 receipts 寫入公開文件；
- 在 runtime date/symbol 選擇下使用非精確來源的 chart fallback。

## Public docs 更新

- `docs/LIVE_MONITOR_SIDECAR.md` — 新增公開 sidecar contract。
- `README.md` — 補上 live monitor sidecar 入口與 docs map。
- `docs/ARCHITECTURE.md` — 補上 ReadOnlyDashboardSidecar runtime layer 與安全邊界。
- `docs/TOPOLOGY.md` — 補上 sidecar docs、dashboard module、test contract 與 cross-link。

## 驗證

本階段 closure 前應至少維持：

```bash
uv run pytest tests/test_dashboard.py -q
uv run ruff check src/steamer_card_engine/dashboard/runtime_chart.py \
  src/steamer_card_engine/dashboard/runtime_store.py \
  src/steamer_card_engine/dashboard/runtime_index.py \
  src/steamer_card_engine/dashboard/runtime_store_cli.py \
  src/steamer_card_engine/dashboard/api.py tests/test_dashboard.py
npm --prefix frontend run build
./frontend/node_modules/.bin/tsc --noEmit -p frontend/tsconfig.json
```

公開文件 push 前另需做 sensitive-string scan，確認沒有主機 IP、雲端帳號、私有 bucket、instance id、內部部署路徑或 raw private receipts 被放進公開 docs。

## 五氣朝元 stale-rule sweep

Changed truth：dashboard/live monitor 是 read-only sidecar，不是交易控制面。

Surfaces checked / amended：

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/TOPOLOGY.md`
- `docs/LIVE_MONITOR_SIDECAR.md`
- dashboard runtime-store code/tests

Retired stale rule：無需刪除歷史 tech-notes；它們是 development history。新的 canonical public contract 是 `docs/LIVE_MONITOR_SIDECAR.md`。

Topology delta：repo-level public topology changed by documenting sidecar boundary and runtime-store importer. Broker / execution authority unchanged.

## 後續

- 前端補 decision aggregate panel。
- runtime store retention / VACUUM policy。
- 若擴大 latest window，先補容量與 retention guard。
- decisions/orders 的 source path normalization 可後續接上 `source_files`。
