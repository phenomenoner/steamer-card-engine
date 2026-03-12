# Outline — steamer-card-engine overview

## 0) TL;DR
- 這不是另一個「幫你直接自動交易」的 repo。
- 它要做的是把台股日內策略系統裡最容易纏死的責任邊界先產品化。
- Card / Deck / AuthSessionManager / MarketDataHub / FeaturePipeline / RiskGuard / ExecutionEngine / ReplayRunner 各有責任。
- agent 可以幫忙 authoring / validation / replay / setup，但 live authority 要留在 operator plane。

## 1) Hook
- 很多策略系統不是輸在策略想法，而是輸在架構把所有東西纏成一團。
- 在日內交易裡，這種纏結不是醜而已，而是 replay 不可信、risk 不可驗、live 權限不清、延遲路徑不可控。

## 2) The real problem
- 表面問題：需要更多策略、更多 agent、更多自動化。
- 真正問題：共享行情、session、feature、risk、execution、replay 沒有乾淨邊界。

## 3) The approach
- docs-first / spec-first
- card-oriented runtime
- intent-first
- replay-first
- operator-governed / agent-assisted

## 4) Product shape
- 產品是什麼 / 不是什麼
- v0.1 已有什麼
- 主要角色：operator / researcher / agent-assisted workflow

## 5) Architecture
- Authoring / Management Plane
- Execution Plane
- 核心組件逐一解釋
- 為什麼 feature/synthesizer 要平台化

## 6) Safety and authority
- shared auth/session
- API key 模式的安全邊界
- card 不能直接下單
- active account + user_def routing hygiene
- day-trading guardrails

## 7) Why replay-first matters
- record / replay / live-sim 不是事後補洞
- replay credibility 取決於 receipts / artifacts
- 這個 repo 為何先把 contract 講清楚再擴 live

## 8) What exists today
- docs contracts
- manifest validation / inspect CLI
- examples / skeleton
- 什麼還沒做完

## 9) Migration path
- 從既有 Steamer stack 遷移，不做 big-bang rewrite
- 目前新 repo 在遷移計畫中的角色

## 10) Close
- 這個產品真正想做的，不是神奇自動交易，而是讓日內策略 runtime 變得能被設計、驗證、回放、治理。