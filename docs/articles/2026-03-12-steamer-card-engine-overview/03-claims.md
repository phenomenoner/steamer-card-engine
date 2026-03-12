# Claims table — steamer-card-engine overview

| # | Claim (verbatim) | Type | Status | Source / method | Assumptions (if estimate) | Notes |
|---|------------------|------|--------|------------------|----------------------------|-------|
| 1 | `steamer-card-engine` 是 docs-first / spec-first 的 seed runtime，而不是 production-ready live-trading framework。 | fact | verified | `README.md`, `docs/PRODUCT_SCOPE.md`, `docs/TOPOLOGY.md` |  | README 與 scope / topology 都明確區分 contract vs placeholder。 |
| 2 | 產品核心立場是 card-oriented、intent-first、replay-first、operator-governed。 | fact | verified | `README.md`, `docs/PRODUCT_SCOPE.md`, `docs/ARCHITECTURE.md`, `docs/CARD_SPEC.md` |  | 多份文件一致。 |
| 3 | Card 可以宣告 symbol pool、risk policy、capital controls、feature requirements，但不能直接下 broker order。 | fact | verified | `docs/CARD_SPEC.md` |  | Card behavior rules 有明文。 |
| 4 | Authoring / Management Plane 與 Execution Plane 的拆分，是產品主要安全邊界之一。 | causal | verified | `docs/ARCHITECTURE.md` |  | Architecture 直接寫明「not cosmetic」。 |
| 5 | shared auth/session 與 shared market-data 應該是平台能力，而不是每張 card 各自處理。 | causal | verified | `README.md`, `docs/AUTH_AND_SESSION_MODEL.md`, `docs/ARCHITECTURE.md` |  | 多份文件同向。 |
| 6 | API key 模式可形成 agent-assisted setup 與 live trading 權限之間的安全邊界。 | causal | verified | `docs/AUTH_AND_SESSION_MODEL.md`, `docs/ADAPTER_SPEC.md`, `docs/PRODUCT_SCOPE.md` |  | 文件表述為安全 posture / practical boundary。 |
| 7 | 日內交易裡的 emergency stop、forced exit、flatten 與 routing hygiene 是架構問題，不是 config 裝飾。 | causal | verified | `docs/DAYTRADING_GUARDRAILS.md`, `docs/ARCHITECTURE.md`, `docs/ADAPTER_SPEC.md` |  | 文件明確這樣定義。 |
| 8 | 目前 CLI 已有 auth/card/deck/global 的 validate / inspect；replay/operator execution 仍是 placeholder。 | fact | verified | `README.md`, `docs/CLI_SPEC.md`, `docs/TOPOLOGY.md` |  | 現況描述一致。 |
| 9 | 這個 repo 的遷移策略不是 big-bang rewrite，而是從既有 Steamer stack 抽出清楚 contract 逐步遷移。 | fact | verified | `docs/MIGRATION_PLAN.md` |  | 文件明確反對 big-bang rewrite。 |