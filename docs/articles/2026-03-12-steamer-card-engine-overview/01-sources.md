# Source log — steamer-card-engine overview

1. `README.md`
   - 產品定位總覽；清楚說明這不是 production-ready 自動交易系統，而是 docs-first seed runtime。

2. `docs/PRODUCT_SCOPE.md`
   - 產品 thesis、使用者角色、v0.1 scope / non-goals、success criteria。

3. `docs/ARCHITECTURE.md`
   - 兩個 plane、核心 component、權限邊界、observability 與 latency posture。

4. `docs/CARD_SPEC.md`
   - Card / Intent contract；說明 card 是最小策略單位，但不能直接碰 broker order flow。

5. `docs/ADAPTER_SPEC.md`
   - Auth / MarketData / Broker adapter 的責任邊界，以及 active account + `user_def` 的 routing hygiene。

6. `docs/AUTH_AND_SESSION_MODEL.md`
   - 為什麼 auth/session 要抽成共享邏輯；Mode A / Mode B 的安全邊界；logical session 的能力模型。

7. `docs/DAYTRADING_GUARDRAILS.md`
   - 為什麼 emergency stop、forced exit、final-auction flatten 不是 config 裝飾，而是架構前提。

8. `docs/CLI_SPEC.md`
   - 現有 CLI 命名與治理方向；目前已實作 validate/inspect，replay/operator 仍是 placeholder。

9. `docs/MIGRATION_PLAN.md`
   - 從既有 Steamer stack 遷移到新 repo 的分期方式；避免 big-bang rewrite。

10. `docs/TOPOLOGY.md`
   - repo 現況：哪些是 source-of-truth contract，哪些仍是 placeholder/stub。

## Evidence posture
- 本文所有具體產品/架構主張都以 repo 內文件為主。
- 對於尚未完成的 runtime / replay / operator / live control，會明確寫成「目標 / 路線 / placeholder」，不寫成已完成能力。