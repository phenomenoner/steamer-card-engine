# steamer-card-engine

> **台股日內策略卡 runtime 種子專案**  
> A docs-first seed runtime for Taiwan cash intraday strategy cards.

`steamer-card-engine` 不是在賣「馬上可上線的自動交易系統」。

它比較像一個**產品骨架**：先把 Card / Deck / Adapter / Session / Replay / Risk 這些邊界定清楚，讓後續實作能夠低延遲、可回放、可審核、可逐步接近 live，而不是把既有單體腳本越疊越重。

## 這個 repo 想解的問題

目前很多台股日內執行系統，會長成這樣：

- 策略邏輯、風控、下單、連線管理纏在一起
- 每個策略自己管 symbol、自己接行情、自己記狀態
- replay 與 live 行為不夠接近
- agent 可以幫很多忙，但權限邊界不清楚

這個 repo 的主張很簡單：

1. **共享 market data 與共享 session/auth 應該是平台能力，不是每張卡自己處理。**
2. **Card 應該表達策略意圖與策略參數，不應直接摸 broker order flow。**
3. **record / replay / live-sim 要是第一級能力，不是事後補洞。**
4. **低延遲在日內交易裡不是 optional feature，而是架構前提。**
5. **agent 可以協助 authoring、validation、replay、設定整理，但 live 權限必須留在 operator plane。**

## 這個 repo 是什麼 / 不是什麼

### 是什麼

- 台股現股日內場景的 **card-oriented runtime seed**
- **docs-first / spec-first** 的產品化起點
- 一個把既有 Steamer 執行經驗拆成可實作 contract 的地方
- 未來 CLI、replay runner、adapter shim、operator workflow 的共用骨架

### 不是什麼

- 不是已完成的 live-trading framework
- 不是任意 agent 可直接控制實盤下單的系統
- 不是 multi-broker / multi-market 的通用終局架構
- 不是在 README 裡假裝「production-ready」的那種東西

## v0.1 產品承諾

v0.1 先把幾件關鍵事情說清楚：

- **Card 是最小策略單位**，有自己的版本、symbol pool、entry/exit 規則、資金限制與 replay 身分。
- **Deck 是治理單位**，決定哪些 card 一起啟用、如何覆寫 symbol universe、如何套用共用 risk policy。
- **Session/Auth 是共享模組**，盡量一次驗證、共用到 marketdata + trading/account surfaces。
- **Feature/Synthesizer 是平台模組**，像 MACD 這類時間序列合成不直接塞進每張 card 的熱路徑裡。
- **Market data 可錄製、可回放**，策略執行至少要支援 replay sim 與 live sim。
- **風控與執行是 operator-governed**，包含 emergency stop、forced exit、final-auction flatten 等日內護欄。

## 高階架構

```text
Authoring / Management Plane
  CLI ── Card Spec ── Deck Spec ── Global Config ── Replay Jobs
   │
   └── validates, versions, inspects, replays, prepares

Execution Plane
  AuthSessionManager
      ├── MarketDataAdapter -> MarketDataHub -> FeaturePipeline -> CardRuntime
      └── Broker/Account Adapter -------------------------------> ExecutionEngine

  CardRuntime -> IntentAggregator -> RiskGuard -> ExecutionEngine -> BrokerAdapter
          │              │               │                │
          └──── Recorder / Audit Trail / ReplayRunner / LiveSim ───────────────┘
```

重點不是 diagram 漂亮，而是責任分工：

- **Card 產生 Intent，不直接下單。**
- **MarketDataHub 管共享訂閱，不讓每張卡自己亂接行情。**
- **FeaturePipeline 產生共用特徵，避免每張卡各算一份 MACD。**
- **RiskGuard / ExecutionEngine 決定哪些意圖能變成實際 broker action。**
- **Recorder / ReplayRunner 讓策略變更能回頭驗證。**

## Card 模型：不只 entry gate

這個 repo 裡的 Card，預期要能描述的不只是「什麼時候進場」，還包括：

- entry gates
- stop-loss / take-profit
- intraday forced-exit timing
- symbol pool
- capital control（例如單筆金額、當日總花費上限）
- required features / synthesizers（例如 1m bar、MACD）

我們的設計建議是：

- **card 負責宣告需求與決策邏輯**
- **synthesizer / feature generation 由平台模組負責**

這樣做的好處很實際：

- replay / live 用同一套 feature contract
- 指標計算不會在多張卡之間重複做熱路徑工作
- 可以更清楚記錄「卡看到了什麼」與「平台合成了什麼」

## Auth / 權限立場

v0.1 文件明確支持至少兩種常見登入模式：

1. `account + password + cert + cert password`
2. `account + API key + cert + cert password`

第二種模式有一個很有用的安全邊界：

- 使用者可以在 API key 層 **關閉交易權限**
- 讓 agent 協助設定、驗證、訂閱、replay、dry-run
- 但仍不把實際交易權限直接交出去

這跟 repo 的核心立場一致：**agent-assisted，不等於 agent-autonomous live trading**。

## Day-trading guardrails

日內交易沒有護欄，架構再漂亮也只是會跑得更快的事故。

v0.1 docs 把這些列為一級需求：

- emergency stop-loss（例如：相對開盤價百分比，或距離漲跌停價 n ticks）
- intraday forced exit（卡片可定義何時開始平倉）
- global final-auction flatten（例如 Asia/Taipei 13:25–13:30 進入尾盤平倉模式）
- active account + `user_def` 過濾，避免混入別的卡 / 別的帳號的 order lifecycle 事件
- latency-aware hot path，因為像放空鎖漲停、無法回補這類情境，stop 行為本身就高度延遲敏感

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
│   ├── MIGRATION_PLAN.md
│   ├── AUTH_AND_SESSION_MODEL.md
│   └── DAYTRADING_GUARDRAILS.md
├── examples/
│   ├── cards/
│   ├── decks/
│   ├── config/
│   └── profiles/
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

目前 CLI 仍是 **placeholder scaffold**，存在的目的主要是固定命令面與 package 形狀，不代表 runtime 已完成。

## 文件導覽

- Product scope: [`docs/PRODUCT_SCOPE.md`](docs/PRODUCT_SCOPE.md)
- Architecture: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- Card contract: [`docs/CARD_SPEC.md`](docs/CARD_SPEC.md)
- Adapter contract: [`docs/ADAPTER_SPEC.md`](docs/ADAPTER_SPEC.md)
- CLI contract: [`docs/CLI_SPEC.md`](docs/CLI_SPEC.md)
- Auth/session model: [`docs/AUTH_AND_SESSION_MODEL.md`](docs/AUTH_AND_SESSION_MODEL.md)
- Day-trading guardrails: [`docs/DAYTRADING_GUARDRAILS.md`](docs/DAYTRADING_GUARDRAILS.md)
- Migration plan from current engine: [`docs/MIGRATION_PLAN.md`](docs/MIGRATION_PLAN.md)

## Current status

- ✅ Public product positioning tightened
- ✅ Core docs/spec contracts defined
- ✅ Shared auth/session and day-trading guardrail docs added
- ✅ Python package skeleton exists
- ⏳ Manifest validation and inspect commands
- ⏳ Replay runner MVP
- ⏳ Shared adapter shims from current TW cash stack
- ⏳ Controlled live-sim / operator workflow

## English summary

`steamer-card-engine` is a docs-first seed repository for a card-oriented runtime focused on Taiwan cash intraday strategy operations.

The repo does **not** claim live-trading readiness. Its job is to make the architecture legible and implementation-friendly:

- shared auth/session and market-data connection management
- cards that emit intent instead of broker orders
- a separate feature/synthesizer layer for replay/live parity
- recordable market data and replay/live-sim execution paths
- explicit day-trading guardrails and operator-governed live authority

If you want agents to help draft cards, adjust decks, validate config, and run replay, this repo is pointed in the right direction.

If you want arbitrary agents to directly control live order flow, this repo is intentionally **not** that.
