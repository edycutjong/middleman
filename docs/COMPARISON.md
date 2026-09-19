# How Middleman differs from its nearest neighbours

Six entries in the Build with CMC: API Hackathon gallery sit closest to this one — three in the
same track, one built on the same feed, two that touch DEX data from the side. Each is named
with what it does, from its own public BUIDL page, and the exact boundary with Middleman.
Written 2026-09-19 from the public gallery as scanned on 2026-09-18; every entry is editable
until the deadline, so read theirs too.

| Entry | Track | What it does | The boundary with Middleman |
|---|---|---|---|
| **Elephant Tracks** (BUIDL 48344, same author) | Data and Visualisation | Splits a token's DEX swaps by maker address and reports **who owns each side** of net flow — one wallet as 62 % of the sell side while net flow reads "balanced". | Same keyless feed (`/v1/dex/tokens/transactions`), different question. Elephant sums `v` per maker *per side* and never uses print order. Middleman orders prints by `(h, lgid)` inside a block and joins a wallet's *consecutive* legs — it asks who stood **between** two prints, not who owned a side — and ends in a routing decision (pool + slippage cap) rather than a concentration share. Neither result can be derived from the other. |
| **Baserate** (48763) | Markets and Trading Tools | A backtested screener over 760 days of top-1000 listing snapshots: the historical base rate of each preset ("rank climbers: median −4.9 %, 37 % hit rate"), with a per-token DEX wallet-concentration sidebar. | Index-level and historical; its subject is *what happened after a screen fired*. Middleman is per-pool and per-print, over the last 800 swaps, and its subject is *what a fill costs right now and who is in the way*. Baserate's DEX sidebar is holder concentration; Middleman's is print adjacency — a wallet can hold nothing and still round-trip 29 times. |
| **Divergence** (48779) | Markets and Trading Tools | Records a Voice-vs-Money gap every 15 minutes — fear-and-greed against derivatives positioning — into four named quadrants, with a decision log and 976 recorded samples. | Sentiment and CEX derivatives at market level; Middleman is DEX prints at pool level. Both state that they measure rather than predict; Divergence measures a *gap between two aggregates over time*, Middleman measures *rows inside one block*. No shared endpoint. |
| **Crypto Screener** (48868) | Markets and Trading Tools | A screener and alert bot over `/v1/cryptocurrency/listings/latest` and `/v2/cryptocurrency/quotes/latest`, with an exchange cross-reference. | The archetype the track description names. It ranks tokens by listing-level fields; Middleman ranks the *pools of one token* by what an organic fill pays after the same-wallet legs are removed. A screener tells you which token; Middleman tells you which pool and what cap. |
| **Signal Desk** (48805) | Real World Assets | An RWA issuer explorer with a breadth-vs-sentiment view and a live capability probe that fires 20 endpoints and classifies each as ok / plan-gated / bad-request. | Touches the DEX family only through `/v1/dex/platform/list`, the new-pairs and gainer-loser lists — never a swap row. Its DEX use is a count of networks; Middleman's is the per-swap maker join. Signal Desk's capability probe and Middleman's `/evidence` page share one instinct — show every call — applied to different products. |
| **Argus** (48875) | AI Agents and Automation | An anomaly detector with an 18-tool agent and a deterministic `explain_move` that splits a token's move into beta-to-BTC, sector excess and coin-specific residual, with the call receipt beside each answer. | Explains *why a price moved* at index level from quotes, OHLCV and categories; Middleman explains *why a fill cost what it did* at pool level from swap rows. Argus rehearses a Basic-tier credit budget for judging; Middleman needs no key at all, so the question does not arise. |

## What nobody else in the gallery does

As of the 2026-09-18 gallery scan (19 approved entries) no other entry reads `/v1/dex/tokens/transactions` for its **order** — the
block and the log index — or joins consecutive prints on the maker address. The DEX endpoint
family appears in three entries and always as a sidebar (a concentration figure, a network
count, a gainers list). Middleman's whole product is that one feed's row order.

## What Middleman deliberately does not do

- **No prediction.** It reports the last 800 prints and a rule-derived route; it never
  forecasts a price or a fill.
- **No wallet labelling.** A round-trip is a shape — same wallet, same block, opposite sides,
  size-matched. The rows are printed; nobody is named a bot.
- **No composite score.** One row per pool with the raw counts and the basis points; the
  route is the argmin of one column under a stated floor, and when no pool clears the floor the
  rule is printed, not widened.
- **No key.** Every endpoint is on the keyless `/public-api` surface, so the demo cannot be
  blocked on a credential and every receipt reports 0 credits.
