# 把台股日內策略從腳本堆，拉回產品架構：steamer-card-engine 的設計理念與整體架構

如果你看過夠多交易系統，會發現真正把團隊拖垮的，常常不是策略本身，而是策略外面的那團東西：登入、行情、風控、回放、下單、帳號切換、權限、紀錄、還有那種「先跑再說，之後再整理」留下來的長年技術債。

`steamer-card-engine` 想處理的，正是這一團。

它不是在賣一個「馬上可上線的自動交易系統」，也不是在包裝一個 agent 可以直接接管實盤的黑盒子。它現在更接近一個 **docs-first、spec-first 的產品骨架**：先把台股日內策略 runtime 最重要的責任邊界講清楚，讓後續實作不是在舊腳本上一路疊補丁，而是有一套可以驗證、可以回放、可以治理、也可以逐步接近 live 的產品化路徑。[來源：`README.md`](../../../README.md)、[`docs/PRODUCT_SCOPE.md`](../../PRODUCT_SCOPE.md)

---

## 問題不只是「策略不夠多」，而是系統把太多責任纏在一起

很多日內策略系統，剛開始都很合理：先做一個能跑的執行器，先把行情接進來，先把策略寫上去，先能下單，先能記錄。問題在於，只要策略開始變多、帳號開始變多、replay 開始變重要、agent 開始參與設定與驗證，這套東西很快就會露出本質：

- 策略邏輯、風控、execution、order lifecycle 全黏在一起
- 每個策略都在自己接行情、自己算指標、自己管 symbol pool
- replay 與 live-sim 路徑長得不像 live
- 權限邊界不夠明確，尤其一旦把 agent 拉進來就更危險
- 共享 market data、shared session、recording 這種平台能力，被誤當成每張策略卡自己處理的小事

這也是 `steamer-card-engine` 的核心判斷：**真正要產品化的，不是某一張策略卡，而是策略卡周圍那個 runtime。** 你要讓 Card、Deck、Auth、MarketData、Feature、Risk、Execution、Replay 這些層級各自有清楚 contract，後面才有資格談可重用、可回放、可審核、可逐步接近 live。[來源：`README.md`](../../../README.md)、[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`docs/MIGRATION_PLAN.md`](../../MIGRATION_PLAN.md)

---

## 這個產品到底是什麼？

一句話講，`steamer-card-engine` 是一個面向 **台股日內策略操作** 的 **card-oriented runtime seed**。

它的產品承諾，不是「替你神奇賺錢」，而是幾個更硬的東西：

1. **shared auth/session 與 shared market-data connection 是平台能力，不是每張 card 自己處理**
2. **Card 是策略單位，但只表達 intent，不直接碰 broker order flow**
3. **Replay / live-sim / recordability 是第一級能力，不是之後再補**
4. **低延遲在日內交易裡不是 optional feature，而是架構前提**
5. **agent 可以協助 authoring、validation、replay、setup，但 live authority 必須留在 operator plane**

也因此，它很明確地劃了一條線：

- **它是什麼**：一個 docs-first 的 seed runtime、一個 card/deck/auth/global contract 的產品起點、一個把 Steamer 既有執行經驗拆成可治理元件的地方。
- **它不是什麼**：不是 production-ready live-trading framework、不是任意 agent 可直接操控實盤的系統、也不是把 README 寫得很像成品的那種 repo。[來源：`README.md`](../../../README.md)、[`docs/PRODUCT_SCOPE.md`](../../PRODUCT_SCOPE.md)

---

## 它的核心設計，不是多一張策略卡，而是把 runtime 切成兩個 plane

`steamer-card-engine` 的架構主張很乾脆：**Authoring / Management Plane** 跟 **Execution Plane** 必須分開。這不是畫圖好看，而是整個產品的安全邊界。

### 1. Authoring / Management Plane
這一層負責的是：

- card manifests
- deck composition
- global config
- auth profile validation
- replay orchestration
- versioning / packaging
- operator-reviewed activation changes

它的介面主要是 CLI、config files、replay artifacts、audit logs。簡單講，這層是「怎麼定義這個系統」，不是「怎麼在盤中真的把單送出去」。[來源：`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`docs/CLI_SPEC.md`](../../CLI_SPEC.md)

### 2. Execution Plane
這一層才處理真正在執行路徑上的事：

- 一次登入，分發共享 session context
- ingest market data
- 正規化市場事件
- 合成 features / time-series views
- 評估 cards
- 聚合 intents
- 套用 risk policy
- 產生 execution requests
- 跟 broker adapters 互動

這裡有一個非常關鍵的設計選擇：**Card 不是 order submitter，而是 intent producer。** 也就是說，策略卡的責任是說「我想做什麼、為什麼、在什麼條件下」，但它不能直接呼叫 broker。真正決定能不能變成 broker action 的，是後面的 `IntentAggregator`、`RiskGuard`、`ExecutionEngine`。[來源：`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`docs/CARD_SPEC.md`](../../CARD_SPEC.md)

---

## 幾個最值得記的 component

### Card
Card 是最小策略單位。它有自己的版本、策略家族、symbol pool、參數、capital controls、risk policy、feature requirements。它讀取 normalized runtime context 與 feature snapshots，輸出 `Intent`。

但 Card 有幾個不能做的事：

- 不能直接呼叫 broker
- 不能直接碰 credentials
- 不能偷改 global policy
- 不能自己開 transport connection

這個限制不是保守，而是為了避免策略單位跟執行權限混成一團。[來源：`docs/CARD_SPEC.md`](../../CARD_SPEC.md)

### Deck
Deck 不是策略本身，而是治理單位。它決定哪些 cards 一起跑、怎麼覆寫 symbol universe、怎麼套用共用 risk/capital policy。這讓 card 可以保持策略意圖，deck 則負責「這些策略一起運作時，整體要怎麼被管」。[來源：`docs/CARD_SPEC.md`](../../CARD_SPEC.md)、[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)

### AuthSessionManager
這一層很容易被低估，但其實超重要。因為在交易系統裡，如果 marketdata、trading、account surfaces 被當成彼此無關的登入，接下來你會得到：重複 credential handling、能力檢查不一致、reconnect 更難、operator 可視性更差。

所以這個 repo 把 **shared logical session** 拉成一級概念。即使底層 vendor 不一定真的給你同一顆 token，它在 runtime 上也要表現成一個清楚的 `SessionContext`：你現在是哪個 account、哪種 auth mode、market data 能不能用、trade permission 有沒有開、session 現在是健康還是快過期。[來源：`docs/AUTH_AND_SESSION_MODEL.md`](../../AUTH_AND_SESSION_MODEL.md)、[`docs/ADAPTER_SPEC.md`](../../ADAPTER_SPEC.md)

### MarketDataHub + FeaturePipeline
另一個很關鍵的選擇是：**共享行情與共享 feature synthesis 必須平台化。**

這背後的理由其實很務實：如果每張卡都自己接行情、自己算 MACD、自己維護時間序列狀態，後果通常不是靈活，而是：

- 熱路徑重複計算
- replay / live feature parity 變差
- 一旦出問題，不知道卡看到的是什麼、平台看到的是什麼

所以 `FeaturePipeline / Synthesizers` 被放在平台層，而不是讓每張 card 私下各算一份。Card 仍然可以保有小型 local state，但共用 time-series / indicator synthesis 應該交給平台。[來源：`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`docs/CARD_SPEC.md`](../../CARD_SPEC.md)

### RiskGuard + ExecutionEngine
這是整個產品能不能被信任的核心。`RiskGuard` 負責套 engine-level / deck-level / card-level 風控；`ExecutionEngine` 則負責把被批准的 intent 變成 execution requests，處理 fills、cancels、replaces、rejects 與 lifecycle routing。

這裡還有一個從舊 Steamer stack 帶來的硬經驗：**active account + `user_def` routing hygiene 不是可有可無。** 如果 order changes、fills、active reports 混在一起，而 runtime 又沒有用 active account 與 `user_def` 正確過濾，你很容易讓 A 卡讀到 B 卡的 lifecycle，或者把不同 account 的事件混在一起。[來源：`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)、[`docs/ADAPTER_SPEC.md`](../../ADAPTER_SPEC.md)、[`docs/MIGRATION_PLAN.md`](../../MIGRATION_PLAN.md)

---

## 為什麼這個產品一直強調「agent-assisted，但 operator-governed」？

因為在這個場景裡，agent 真正擅長的事情，跟它不該碰的事情，界線其實很清楚。

它可以很適合幫忙：

- 草擬 cards
- 驗證 manifests
- 整理 auth profile shape
- 準備 replay jobs
- 分析 receipts
- 協助 config / docs / setup

但這不代表它就該直接拿 live authority。

這也是 repo 很重視 auth mode B 的原因：`account + API key + cert + cert password` 在某些 broker 生態裡，可以把 API key 權限縮小，讓 agent 協助 setup/replay/dry-run，但不直接握有交易權限。這不是小技巧，而是一條產品級安全邊界。[來源：`docs/AUTH_AND_SESSION_MODEL.md`](../../AUTH_AND_SESSION_MODEL.md)、[`docs/ADAPTER_SPEC.md`](../../ADAPTER_SPEC.md)、[`docs/PRODUCT_SCOPE.md`](../../PRODUCT_SCOPE.md)

---

## 在日內交易裡，guardrails 不是加分題，而是架構前提

這個 repo 有一個我很認同的立場：**day-trading guardrails 不是 config 裝飾，而是 architecture concern。**

像這幾個能力，它都當成第一級需求來談：

- emergency stop-loss
- intraday forced exit
- final-auction flatten mode
- capital controls
- mixed order-event routing hygiene

尤其短線日內交易，exit path 其實比 entry 更決定系統值不值得信。你可以進得很漂亮，但如果在放空鎖漲停、流動性消失、尾盤 flatten 這些情境下，系統的 exit behavior 既不低延遲、也不可觀測，那整套東西再優雅都只是更快地出事。[來源：`docs/DAYTRADING_GUARDRAILS.md`](../../DAYTRADING_GUARDRAILS.md)、[`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)

---

## 為什麼是 docs-first，而不是直接先把 runtime 寫出來？

因為這個 repo 的前提不是綠地發明，而是 **把既有 Steamer stack 產品化**。`docs/MIGRATION_PLAN.md` 很誠實地寫了：現有 `sdk_manager_async.py`、`strategy_async.py`、`magicbox/gates.py`、`magicbox/recorder.py` 已經有真實價值，假裝可以整包丟掉、重寫一個更乾淨的版本，其實是自欺。

所以這個 repo 先做的，是把遷移過程的 target contracts 固定下來：

- 現有 login / websocket orchestration → 未來的 `AuthSessionManager`、`MarketDataAdapter`、`MarketDataHub`
- 現有 strategy host + risk + execution 混合物 → 拆成 `CardRuntime`、`IntentAggregator`、`RiskGuard`、`ExecutionEngine`
- 現有 recorder → 未來 replay / audit 的 receipts 與 artifact model

也就是說，docs-first 在這裡不是拖延，而是 **先把邊界凍結，再避免未來把 legacy 行為直接硬編碼進錯的 abstraction**。[來源：`docs/MIGRATION_PLAN.md`](../../MIGRATION_PLAN.md)、[`docs/TOPOLOGY.md`](../../TOPOLOGY.md)

---

## 現在做到哪？什麼還沒做？

截至目前，這個 repo 已經有幾個很關鍵的 seed：

- 產品與架構說明文件
- card / deck / auth / global 的 contract docs
- manifest validation / inspect CLI
- examples 與 package skeleton
- 測試把目前 CLI 與 validation shape 釘住

但它也非常清楚哪些東西還沒做完：

- replay / live-sim 仍是方向，不是完整 runtime
- operator commands 還是 placeholder
- runtime component names 已命名，但尚未完整實作 conflict resolution / risk / execution
- replay credibility 還要靠穩定 receipts / artifacts 才能成立

這種誠實很重要。因為市場上最不缺的，就是一堆把 roadmap 寫成已完成能力的產品敘事；真正稀缺的，反而是這種知道自己現在是 seed、知道什麼是 contract、也知道什麼還只是 promise 的 repo。[來源：`docs/CLI_SPEC.md`](../../CLI_SPEC.md)、[`docs/TOPOLOGY.md`](../../TOPOLOGY.md)、[`README.md`](../../../README.md)

---

## 我會怎麼看 steamer-card-engine 的價值

如果只用一句很短的話來總結，我會這樣說：

> `steamer-card-engine` 真正想做的，不是把交易變成更酷的腳本，而是把台股日內策略 runtime 變成一個能被設計、驗證、回放、治理的產品。

它的價值不在於「現在就能 live」，而在於它把幾個最容易被忽略、但一旦忽略就會很痛的東西，提前變成了產品邊界：

- Card 只表達 intent，不直接下單
- replay / live-sim / live 必須共享核心 vocabulary
- shared session、shared market data、shared features 是平台能力
- agent 可以參與，但 live authority 必須被 operator plane 接住
- latency、forced exit、flatten、routing hygiene 都是架構問題，不是日後再補的細節

如果這些邊界先定住，後面的 replay runner、adapter shim、operator workflow、甚至更完整的 live posture，才有機會長成一個可信的系統。反過來說，如果這些邊界沒先清楚，越往後做，系統就越容易回到那種「其實能跑，但沒人真的敢擴」的老路。

---

## 依據文件 / 延伸閱讀

- [`README.md`](../../../README.md)
- [`docs/PRODUCT_SCOPE.md`](../../PRODUCT_SCOPE.md)
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md)
- [`docs/CARD_SPEC.md`](../../CARD_SPEC.md)
- [`docs/ADAPTER_SPEC.md`](../../ADAPTER_SPEC.md)
- [`docs/AUTH_AND_SESSION_MODEL.md`](../../AUTH_AND_SESSION_MODEL.md)
- [`docs/DAYTRADING_GUARDRAILS.md`](../../DAYTRADING_GUARDRAILS.md)
- [`docs/CLI_SPEC.md`](../../CLI_SPEC.md)
- [`docs/MIGRATION_PLAN.md`](../../MIGRATION_PLAN.md)
- [`docs/TOPOLOGY.md`](../../TOPOLOGY.md)