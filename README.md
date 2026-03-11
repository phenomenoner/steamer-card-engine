# steamer-card-engine

> **以卡片（Card）為中心的台股日內策略執行種子專案**  
> A card-oriented runtime seed for Taiwan cash intraday strategy operations.

`steamer-card-engine` 想把目前偏單體、單策略、單 API 連線的交易執行世界，整理成一個比較像產品的 runtime：

- **單一共享市場資料連線 / Hub**，不要每張策略卡各自亂接。
- **多張策略卡（Cards）共用同一個執行引擎**，但各自保留策略版本、參數、啟停與 replay 能力。
- **CLI 可管理卡片、牌組（Deck）、全域設定**，方便代理人與研究流程協作。
- **即時執行、風控、下單權限仍屬於操作面（operator plane）**，不是把 live trading 直接交給任意 agent。
- **券商 / 市場資料 adapter 可替換**，v1 先聚焦台灣現股日內。

這不是「立刻上線自動交易」的 repo。  
這是一個**產品化與介面化**的第一版：先把邊界、責任分工、規格與遷移路線講清楚，再逐步接近 replay、dry-run、最後才是受控 live。

## 為什麼現在做

目前既有引擎已經證明幾件事：

1. **共享 market data 與集中執行是對的。**
2. **策略邏輯與下單 / 風控應該分離。**
3. **回放（replay）與決策記錄，是產品化前的必要資產。**
4. **若未先定義 Card / Deck / Adapter contract，之後會很難安全擴充。**

所以這個 repo 的目標不是多寫幾個策略，而是把「能安全長大」的骨架先搭好。

## v1 範圍

### In scope

- 台灣現股（TW cash）日內交易場景
- replay-first、dry-run-first
- 單一 engine / deck，支援多張 card 與多個變體
- 全域設定 + 卡片設定 + deck 編排
- MarketDataAdapter / BrokerAdapter 抽象層
- CLI 管理 authoring、replay、operator 指令面

### Out of scope / Non-goals

- 期貨、選擇權、海外市場
- 多券商智慧路由
- 任意 agent 直接控制 live order flow
- 任意熱插拔 plugin 系統
- 宣稱已完成的正式 live-trading framework

## 核心概念

- **Card**：策略卡。輸入 market context，輸出 `Intent`，不直接送出 broker order。
- **Deck**：一組一起被啟用、排序、受風控治理的 cards。
- **Global Config**：交易時段、資金、風控、adapter、權限、觀測設定等全域規則。
- **MarketDataAdapter**：把外部行情 API 正規化成 runtime 事件。
- **BrokerAdapter**：把受控的 execution request 映射到券商 API。

## 高階架構

```text
Authoring / Management Plane
  CLI ── Card Spec ── Deck Spec ── Global Config
   │
   └── validates, versions, replays, prepares

Execution Plane
  MarketDataHub -> CardRuntime -> IntentAggregator -> RiskGuard -> ExecutionEngine -> BrokerAdapter
         │                │                │                 │                │
         └──────────── ReplayRunner / Recorder / Audit Trail ────────────────┘
```

重點是：

- **Card 只負責產生意圖（Intent）**。
- **RiskGuard 與 ExecutionEngine 決定哪些意圖可以變成下單行為**。
- **operator plane 持有 live 開關與風控權限**。

## Repo 內容

```text
steamer-card-engine/
├── README.md
├── pyproject.toml
├── docs/
│   ├── PRODUCT_SCOPE.md
│   ├── ARCHITECTURE.md
│   ├── CARD_SPEC.md
│   ├── ADAPTER_SPEC.md
│   ├── CLI_SPEC.md
│   └── MIGRATION_PLAN.md
├── examples/
│   ├── cards/
│   ├── decks/
│   └── config/
└── src/steamer_card_engine/
    ├── cli.py
    ├── models.py
    ├── adapters/base.py
    ├── cards/base.py
    └── runtime/components.py
```

## Quickstart

```bash
uv venv
uv run steamer-card-engine --help
uv run python -m steamer_card_engine --help
```

目前 CLI 是 **placeholder scaffold**，用來固定命令面與 package 形狀，不代表 runtime 已完成。

## 文件導覽

- Product scope: [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Card contract: [`docs/CARD_SPEC.md`](docs/CARD_SPEC.md)
- Adapter contract: [`docs/ADAPTER_SPEC.md`](docs/ADAPTER_SPEC.md)
- CLI contract: [`docs/CLI_SPEC.md`](docs/CLI_SPEC.md)
- Migration plan from current engine: [`docs/MIGRATION_PLAN.md`](docs/MIGRATION_PLAN.md)

## Current status

- ✅ Product thesis and boundary defined
- ✅ Initial docs/spec scaffold committed
- ✅ Python package skeleton created
- ⏳ Replay runner implementation
- ⏳ Adapter shims for current TW cash stack
- ⏳ Controlled dry-run execution path
- ⏳ Live operator workflow

## English summary

`steamer-card-engine` is a seed repository for turning an existing single-engine Taiwan intraday trading stack into a product-shaped runtime.

The core move is to separate:

- **authoring and management** of strategy cards,
- from **execution, risk, and live operator control**.

Cards produce **Intent**, not broker orders. A shared `MarketDataHub` feeds multiple cards, while `IntentAggregator`, `RiskGuard`, and `ExecutionEngine` decide what can proceed. v1 is intentionally narrow: Taiwan cash intraday, replay-first, dry-run-first, one deck/engine, multiple cards/variants, adapter-swappable over time.

## Positioning

如果你想的是「讓 agent 幫忙寫策略卡、改 deck、跑 replay、整理設定」，這個 repo 是對的。  
如果你想的是「讓 agent 隨時直接控制 live 下單」，這個 repo 目前刻意不是那條路。
