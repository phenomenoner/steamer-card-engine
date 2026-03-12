# 我們為什麼做 steamer-card-engine：把台股日內策略系統，重新長成一個產品

今天想正式把 `steamer-card-engine` 這個專案介紹清楚。

如果只用一句話來說，它不是另一個標榜自己「很快就能自動交易」的框架；它更像一個刻意慢下來、先把邊界講清楚的產品骨架。它要處理的，不只是策略怎麼寫，而是整個台股日內策略系統，怎麼從腳本堆與單體執行器，重新長成一個能被理解、被驗證、被回放、也能被治理的 runtime。

這件事我們想了很久，最後得到的結論其實很簡單：**很多交易系統真正的瓶頸，從來不是策略想法不夠多，而是系統把太多責任糊在一起。**

---

## 不是再做一個「更會下單」的東西

交易系統很容易掉進一種很熟悉的路線：

- 先把行情接進來
- 先把策略寫上去
- 先能下單
- 先能記錄
- 先能跑再說

短期看起來合理，長期通常會開始發生幾件事：

- 策略邏輯和 execution 越來越難拆開
- 風控、登入、帳號、狀態、回放全部糊成一團
- 每新增一個策略，就多一份自己的 symbol、自己的指標計算、自己的連線處理
- replay 跟 live 看起來像同一套，其實行為越來越不像
- 一旦把 agent 拉進來，權限邊界也會開始模糊

於是系統雖然「能跑」，但沒有人真的敢把它當產品擴大。它更像一台堆滿實戰經驗、同時也堆滿歷史包袱的機器。

`steamer-card-engine` 想做的，不是把這台機器包裝得更酷，而是承認問題就在這裡：**我們需要先把 runtime 的責任邊界重新整理乾淨。**

---

## 我們想做的，其實是 card-oriented runtime

這個 repo 的核心主張，不是「策略就是一切」，而是：**策略卡（Card）應該只是整個系統裡的一個清楚元件。**

在這個模型裡：

- **Card** 是最小策略單位，負責表達策略意圖
- **Deck** 是治理單位，決定哪些 card 一起啟用、如何套 policy
- **Auth / Session** 是共享能力，不該每張卡自己處理
- **Market data / feature synthesis** 是平台能力，不該每張卡自己重算
- **Risk / execution** 是 operator-governed 的執行平面，不該讓 card 直接碰 broker
- **Replay / live-sim / recordability** 要是第一級能力，不是之後再補的附加品

這樣做的目的，不是為了把架構切得很漂亮，而是為了讓系統終於可以回答一些過去很難說清楚的問題：

- 這個策略到底看到了什麼？
- 這個 decision 是哪個 card、哪個版本、在哪個 feature snapshot 下做的？
- 這個 execution 為什麼會被放行，或為什麼被 risk block？
- replay 與 live-sim 跟 live，到底共享了哪些 contract？
- agent 在這裡可以幫到哪裡，又不能跨到哪裡？

如果一個系統回答不了這些問題，它就很難真的成為產品。

---

## 這個 repo 最重要的一條線：Intent-first，而不是 broker-first

在 `steamer-card-engine` 裡，Card 不應該直接摸 broker order flow。這是很刻意的設計。

我們希望 Card 做的，是：

- 消耗 normalized runtime context
- 讀取平台整理好的 feature / synthesizer outputs
- 依照自己的 parameters、symbol pool、risk hints 做判斷
- 最後輸出 `Intent`

也就是說，Card 說的是：

> 我想進場 / 出場 / 減碼 / 調整，原因是什麼、把握度大概怎樣、 sizing hint 是什麼。

但它不能直接說：

> 幫我送這張單。

中間一定還有幾層：

- `IntentAggregator`
- `RiskGuard`
- `ExecutionEngine`
- `BrokerAdapter`

這條線看起來好像繞遠，但其實很關鍵。因為只要策略卡能直接下單，你幾乎等於承認：策略邏輯、風控邏輯、broker lifecycle、operator authority 最後還是混在一起。那 replay、audit、live safety 就很難乾淨。

---

## 為什麼 shared session / shared market data 這麼重要？

另一個我們特別想先講清楚的，是**共享能力**。

在很多真實系統裡，問題不是策略不會寫，而是每個策略都在自己做同樣的事情：

- 自己登入
- 自己維護 session
- 自己接行情
- 自己管理 symbol subscription
- 自己算一套指標

這種模式一開始很快，但一旦策略數量上來，它就會變成一種很昂貴的隱性成本：

- 重複計算很多次
- replay / live 行為更難對齊
- reconnect / renew / capability checks 更難看清楚
- 連權限狀態都容易變模糊

所以 `steamer-card-engine` 很早就把這件事定義成產品立場：

- `AuthSessionManager` 應該負責共享的 logical session boundary
- `MarketDataHub` 應該負責共享訂閱與事件分發
- `FeaturePipeline` / `Synthesizers` 應該負責共用特徵，不該讓每張 card 各算一份 MACD

這不只是效能優化，而是讓 runtime 的可觀測性與可治理性上得來。

---

## agent 可以幫很多忙，但 live authority 不能被偷渡

這個 repo 還有一個很明確的立場：**agent-assisted，不等於 agent-autonomous live trading**。

我們其實很看重 agent 在這裡能幫忙的地方，例如：

- 草擬與修改 card
- 驗證 manifests
- 準備 replay jobs
- 整理 auth profile
- 做 config / docs / setup 輔助
- 分析 receipts 與調整建議

但這不等於它就應該拿 live trading authority。

所以 repo 裡對 auth/session 的設計也特別強調安全邊界，尤其是支援 `account + API key + cert + cert password` 這一類 login mode。原因不是「比較潮」，而是某些 broker 生態裡，API key 權限可以被切得比較細。這讓 agent 能在 setup / replay / validation 的範圍內工作，但不直接跨進 live trading。

這條線對我們來說不是附註，而是產品哲學的一部分。

---

## 為什麼 replay-first 不是口號，而是必要條件

我們很不想再做一種系統：平常靠直覺運作，一出事才發現 replay 不可信，或 replay 和 live-sim 根本不是同一套世界。

這也是為什麼 `steamer-card-engine` 一開始就把這些東西放在同一條主線上：

- recordable market data
- replay runner
- live-sim path
- stable artifacts / receipts
- feature provenance
- intent / risk / execution receipts

因為如果沒有這些東西，策略系統其實很難進入「可審核」狀態。你可以知道它今天賺或賠，但你不一定知道它到底是怎麼做出這些決定的。對研究、對 operator、對未來任何 agent-assisted workflow，這都不是一個好的地基。

所以我們寧可先把 contracts、artifact shape、component responsibilities 講清楚，也不要急著把 live-ready 的話說太早。

---

## docs-first 不是保守，而是避免把錯的東西寫死

這個 repo 選擇先走 docs-first / spec-first，不是因為我們不想寫 code，而是因為現實上已有一套 Steamer stack 在運作。我們現在做的，不是從零發明一個玩具，而是想把既有實戰經驗裡那些真的重要的東西，抽成更清楚、更穩定的產品 contract。

這件事如果做反了——先寫一堆新的 runtime code，再回頭想邊界——很容易把 legacy 的耦合重新包裝一遍，只是檔名變新而已。

所以 `steamer-card-engine` 現階段最重要的價值，是讓整個產品 shape 先變得清楚：

- 什麼是 Card
- 什麼是 Deck
- 什麼是 shared session
- 什麼是 shared market data
- 哪裡是 risk boundary
- 哪裡是 operator plane
- 哪裡是 replay / live-sim / live 的共同 vocabulary

等這些地基穩了，後續的 replay runner、adapter shim、operator workflow、controlled live-sim，才有機會長成一個真的能被信任的系統。

---

## 現在 repo 裡已經有什麼？

截至目前，`steamer-card-engine` 已經不是只有一句概念而已。它至少已經把幾件重要事情落成 seed：

- 產品 scope 與架構文件
- Card / Deck / Adapter / Auth / CLI contract docs
- manifest validate / inspect CLI
- examples 與 package skeleton
- 對 migration path 的明確規劃

同時，它也很誠實地保留了一條界線：

- replay / operator / live runtime 還在後續路線上
- 現階段不是 production-ready live-trading framework
- 我們不會假裝 placeholder 已經等於能力完成

這種誠實其實很重要。因為對外介紹一個產品時，最容易做的事就是多講一點未來式、少講一點現況。但我們更想做的，是讓大家一眼看出：這個 repo 的強項到底在哪裡，它的 ambition 是什麼，它現在又確實做到哪裡。

---

## 如果要用一句話收斂 steamer-card-engine

我會這樣講：

> `steamer-card-engine` 想做的，不是把交易系統變成更大的腳本，而是把台股日內策略 runtime 變成一個真正能被設計、驗證、回放、治理的產品。

它的野心其實不小，但路線是克制的。

它沒有直接跳去宣稱 live autonomy，也沒有把 agent 直接放進最危險的位置。它先做的是把最容易爛掉的幾條線拉直：

- Card 只負責策略意圖
- shared session / data / features 屬於平台
- risk / execution 必須獨立治理
- replay / live-sim / receipts 必須先站穩
- operator plane 要清楚接住 authority

如果這些事情先做對，後面的功能擴展才有意義；不然只是把同樣的複雜度，換一個 repo 名字重來一次。

---

## 參考文件

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