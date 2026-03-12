# Positioning — steamer-card-engine

- **Working title:** 把台股日內策略從腳本堆，拉回產品架構：steamer-card-engine 的設計理念與整體架構
- **One-sentence promise:** 用一篇中文長文，把 steamer-card-engine 的產品定位、架構分工、安全邊界、演進路線講清楚，讓讀者知道這不是另一個「自動交易黑盒」，而是一個 card-oriented、operator-governed、replay-first 的 runtime 骨架。
- **Format:** narrative + technical overview article

## Audience
- **Primary reader:** 對量化 / 策略工程 / agent workflow / 交易系統產品化有興趣的工程師、研究者、操作員、技術型投資人
- **Prior knowledge:** 知道策略、回測、API、broker、風控這些名詞，但未必熟悉具體 runtime 分層
- **Likely skepticism:**
  - 這是不是又一個包裝得比較漂亮的自動交易系統？
  - docs-first 會不會只是還沒做出東西的說法？
  - agent 參與交易系統，是不是權限一定會失控？

## Positioning
- **Topic / thesis:** steamer-card-engine 的核心不是「幫你自動下單」，而是把台股日內策略執行系統裡最容易纏死的幾個層次——卡片策略、共享行情、登入與 session、風控、回放、operator 權限——先拆成清楚的產品 contract。
- **Why now:** 現有策略腳本與單體執行器一旦開始變多，replay / live / 權限 / 風控 / 共享行情會互相污染；越晚拆邊界，越難補。
- **Competing narratives / alternatives:**
  - 「先做能跑就好，之後再重構」
  - 「每個策略自己接行情、自己下單比較快」
  - 「agent 能寫策略，就順便讓它直連 live trading」
- **What we can safely claim:**
  - 這是一個 docs-first seed runtime
  - 已有 manifest contract、validate/inspect CLI、auth/card/deck/global docs 與 package skeleton
  - 核心立場是 agent-assisted、operator-governed、replay-first、intent-first
- **What we must not claim:**
  - 不是 production-ready live trading framework
  - 不是已完成 replay/live runtime
  - 不是 agent 可直接自治實盤的系統

## Success criteria for the article
- 讀者能在一篇文章內看懂：產品要解什麼、為什麼這樣拆、現在做到哪、接下來怎麼走。
- 文章既有敘事，也能讓工程讀者抓到具體 component 與 contract。
- 重要主張都能對應 repo 內文件來源，不靠空泛口號。