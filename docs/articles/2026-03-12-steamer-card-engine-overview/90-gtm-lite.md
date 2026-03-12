# GTM lite — steamer-card-engine overview

## Headline options
1. 把台股日內策略從腳本堆，拉回產品架構：steamer-card-engine 的設計理念與整體架構
2. steamer-card-engine：不是自動交易黑盒，而是台股日內策略 runtime 的產品骨架
3. 為什麼我們先做 docs-first？steamer-card-engine 想解的不是策略，而是 runtime
4. 從 Card 到 Replay：steamer-card-engine 想怎麼重做台股日內策略系統的邊界
5. agent-assisted，但 operator-governed：steamer-card-engine 的產品設計主張

## TL;DR
`steamer-card-engine` 不是另一個聲稱自己已經能直接實盤上線的交易框架。它更像一個 docs-first、spec-first 的 seed runtime，目標是把台股日內策略系統裡最容易纏死的幾層——Card、Deck、shared auth/session、shared market data、feature synthesis、risk、execution、replay——先拆成清楚的 contract。這個 repo 的重點不是「立刻自動下單」，而是建立一套 intent-first、replay-first、operator-governed 的產品骨架，讓後續實作能被驗證、回放、治理，也能逐步接近 live，而不是在單體腳本上繼續疊技術債。

## Short social copy
- `steamer-card-engine` 想做的不是更花的自動交易，而是把台股日內策略 runtime 先做成一個能被設計、驗證、回放、治理的產品骨架。
- 這個 repo 的關鍵主張很簡單：Card 只表達 intent，不直接碰 broker；shared session / market data / features 是平台能力；agent 可以幫忙，但 live authority 要留在 operator plane。