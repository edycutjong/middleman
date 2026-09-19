<div align="center">

<img src="docs/assets/icon.svg" alt="Middleman icon" width="144">

<h1>Middleman</h1>

<p><em>Who stands between your quote and your fill, per pool.</em></p>

<p align="center">
  <img src="docs/assets/readme-hero-animated.svg" alt="Middleman — names the middleman: two blue prints in one block turn orange the instant the same wallet is found on both sides; 66.2% of the busiest Uniswap v2 pair's volume was 3 wallets buying back what they just sold" width="100%">
</p>

<p>A DEX trader sees a quote and a fill and cannot tell what stood between them — a wallet
printing on both sides of the block, or the pool itself. Middleman orders a token's real
prints by block and log index, joins them on the maker address, names the middleman, and
says where to route and what slippage cap to set.</p>

<p><strong>Live, keyless, 2026-09-18T22:36Z:</strong> CoinMarketCap's #1 Uniswap v2 pair on
Ethereum by transactions was busy with itself — <strong>66.2 % of its volume was 3 wallets
buying back what they just sold, inside one transaction</strong>, 29 times in 3.6 hours. Take
the legs out and an organic fill there pays 15.5 bps, not the 55.3 the raw tape implies.
800 prints in <strong>8.6 s</strong> for <strong>0 credits</strong>.
<a href="DEMO.md">Receipt →</a></p>

<br/>

[![Judge Guide](https://img.shields.io/badge/⚖️_Start-Here-3DDC97?style=for-the-badge)](JUDGE.md)
[![Live page](https://img.shields.io/badge/middleman--cmc.vercel.app-Live-FF7A45?style=for-the-badge)](https://middleman-cmc.vercel.app)
[![Evidence](https://img.shields.io/badge/every_call-Evidence-5AC8FA?style=for-the-badge)](https://middleman-cmc.vercel.app/evidence)
[![API Feedback](https://img.shields.io/badge/📮_CMC_API-Feedback-4C9AFF?style=for-the-badge)](FEEDBACK.md)
[![Built for Build with CMC](https://img.shields.io/badge/DoraHacks-Build_with_CMC-8b5cf6?style=for-the-badge)](https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail)

<br/>

![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat&logo=python&logoColor=white)
![CoinMarketCap](https://img.shields.io/badge/CoinMarketCap_DEX_API-3861FB?style=flat&logo=coinmarketcap&logoColor=white)
![No API key](https://img.shields.io/badge/API_key-not_required-4C9AFF?style=flat)
![Zero dependencies](https://img.shields.io/badge/runtime_deps-zero-5E6C80?style=flat)
![Tests](https://img.shields.io/badge/tests-139-3DDC97?style=flat)
[![License](https://img.shields.io/badge/License-MIT-FFB020?style=flat)](LICENSE)

</div>

---

## See it in action

No key. No signup. No install. One command:

```bash
python3 scripts/middleman.py
```

```
middleman 0.1.0 — keyless, live

hero rule: the base token of the #1 Ethereum Uniswap v2 pair by 24h transactions at capture time
  → MOTO/WETH  0xbd965230588eaa536de6aa45e8ebbc01638535e0

MOTO · ethereum · 800 prints · 3.86 h · blocks 26006381–26007537 · captured 2026-09-18T23:00:20Z · keyless

  27.5% of Uniswap v2 / WETH volume is 1 wallet(s) buying back what they just sold (8 round-trips, same transaction)

  pool                         prints organic  round-trips                sandw  q→fill p50 / p90     tax     liq
  ----------------------------------------------------------------------------------------------------------------
  Uniswap v2 / WETH               771     755  8 · 1 wallet(s) · 27.5%        0  39.2 / 60.8 bps      0/0   $954k  ◀ route
  Uniswap v2 / USDC                16      16  —                              0  70.4 / 137.8 bps     0/0    $39k
  Uniswap v2 / USDT                13      13  —                              0  71.1 / 135.2 bps     0/0    $34k

  ▶ route via Uniswap v2 / WETH · cap slippage at 0.65 %   (organic p90 60.8 bps, 1 candidate pool(s))
    rule: lowest organic p90 quote-to-fill among pools with ≥ 50 organic prints
    coverage: this window is 16% of the routed pool's 24h transactions (4969: 2696 buys / 2273 sells)

  block 26006381 — raw rows (round-trip)
    lgid   633  0x9c97c0a6a0…  sell a0       505,623.1418  a1       0.625752  a1/a0 1.2376e-06  ◀ leg
    lgid   642  0x9c97c0a6a0…  buy  a0       497,596.3088  a1       0.619495  a1/a0 1.2450e-06  ◀ leg
    lgid   721  0xdbde0f745f…  buy  a0           240.4182  a1       0.000300  a1/a0 1.2494e-06
    leg 1  lgid 633  0x9c97c0a6a00b1a9f74dbe09a4c55ec9f09f8af7d  sell  a1/a0 = 0.6257523552405421 / 505623.14176740864 = 1.2375864622280164e-06
    leg 2  lgid 642  0x9c97c0a6a00b1a9f74dbe09a4c55ec9f09f8af7d  buy  a1/a0 = 0.6194948316881366 / 497596.3088161665 = 1.2449747329556753e-06
    same wallet · same block 26006381 · same tx · |Δa0| / a0 = 0.0159 ≤ 0.05 → round-trip

wrote docs/proof/live_run.json  (11.3s wall clock, 0 credits — keyless)
```

> **That is a live call to CoinMarketCap's keyless `/public-api` surface. Nothing here is a
> fixture.** This transcript is from **2026-09-18T23:00:18Z**, receipt at
> [`docs/proof/live_run.json`](docs/proof/live_run.json). The page — and the numbers at the top
> of this file — come from the capture `scripts/seed.py` made **24 minutes earlier** with the
> same engine and the same rule, when the same wallets were **66.2 %** of the pool's volume
> across 29 round-trips ([`docs/proof/moto.json`](docs/proof/moto.json), the 800 raw prints in
> [`data/tape_moto.json`](data/tape_moto.json)). Between the two runs they went quiet. Run it
> yourself and the number will differ again, because it comes from the market rather than from
> this file — and `python3 scripts/verify_tape.py` re-derives every committed receipt from its
> tape with the network unplugged. Walk-through in **[DEMO.md](DEMO.md)**.

**Read the two orange rows.** Same maker, same block, same transaction hash: sell 505,623 MOTO,
buy 497,596 MOTO back, 1.6 % apart. Divide `a1` by `a0` and you have the price each leg paid.
In the capture behind the page that wallet and two others did it 29 times — $127,254 of the
pool's $192,275 — and the pair sits at the top of CoinMarketCap's activity ranking because of them.

---

## The problem and the solution

### The problem

Every DEX tool shows a trader two numbers before a swap — a quote and a slippage tolerance —
and one after: the fill. The gap between them has three possible authors: a sandwicher printing
around her inside the block, a wash bot whose round-trips make a pool look deep, or the pool's
own thinness. Nothing tells her which. So she picks the pool with the most transactions (the one
most likely to be washed) and sets a loose cap "to be safe" (the one thing a sandwicher needs).
Every flow tool prints volume and transaction counts — exactly the numbers a round-tripping
wallet inflates.

### The solution

CoinMarketCap's `/v1/dex/tokens/transactions` returns, per swap and with no key, the **maker
address** (`ma`), the **block** (`h`), the **log index** (`lgid`), the side and both amounts.
Order the prints by `(h, lgid)`, group them into pools by `(venue, base, quote)`, and join on
the maker:

| Shape | Definition | What it is |
|---|---|---|
| **Round-trip** | the same wallet's next print in the block is the other side, size within 5 % | buying back what it just sold — usually inside one transaction |
| **Sandwich** | a round-trip whose legs enclose 1–4 other makers printing in the first leg's direction, and the wallet came out ahead | the prints between were front-run |
| **Organic** | everything else — victims included; their fills are real | what a trader actually pays |

Then, for every organic print, the basis points between the price it paid (`a1 / a0`) and the
print before it in the same pool — the price you saw versus the price you got — p50 and p90
per pool. And one line: **route via the pool with the lowest organic p90, cap slippage at that
p90 rounded up to 0.05 %.**

**The hero is a rule, not a pick.** The page shows whichever token is the base of the pair
CoinMarketCap itself ranks #1 by 24 h transactions on Ethereum Uniswap v2 at capture time.
Whatever that pair is on capture day is what the page shows.

---

## The census — ten tokens, three chains, whatever they said

| Token · chain | Prints | Round-trips | Sandwiches | Route · cap |
|---|---|---|---|---|
| **MOTO** · ethereum — hero by rule | 800 | **29 · 3 wallets · 66.2 % of volume** | 0 | Uniswap v2 / WETH · 0.65 % |
| SHIB · ethereum | 800 | 0 | 0 | ShibaSwap / WETH · 0.65 % |
| PEPE · ethereum | 800 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| UNI · ethereum | 800 | 0 | **1** | Uniswap v3 / WETH · 0.20 % |
| LINK · ethereum | 800 | 0 | **1** | Uniswap v4 / ETH · 0.05 % |
| AAVE · ethereum | 800 | 0 | 0 | Uniswap v3 / WETH · 0.15 % |
| Mog · ethereum | 800 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| SPX · ethereum | 800 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| USDT · bsc — hero by rule | 800 | 13 | 0 | PancakeSwap v4 / KII · 0.05 % |
| USDC · solana — hero by rule | 800 | 3 | 0 | Tessera V / SOL · 0.05 % |

**8,000 prints · 2 sandwiches · 45 round-trips by 14 wallets.** The two sandwiches are the same
wallet, `0xae2fc483…`, front-running a seller on UNI and on LINK in three separate transactions
inside one block each time — for $0.95 and $2.19. The widest spread between one token's pools:
LINK, **22.9×** (0.6 bps median on Uniswap v4 / ETH against 14.2 on Uniswap v3 / USDC).
Every row's receipt is in [`docs/proof/`](docs/proof/) and every receipt re-derives from its tape.

---

## What we got wrong — dated retraction

**2026-09-18.** This project was decided as *the sandwich rate per pool*, with a prediction that
it might be near zero off Ethereum mainnet. The day-1 spike ran the join on 1,200 real prints
and found **zero** same-block sandwiches; the ten-token census found **two in 8,000**. The
pre-authorised fallback — victim overpay on same-block front-runs — measured a median of
0.0 bps. So the headline changed before the build, not the caveat after: the engine is the
same feed, the same ordering, the same maker join; the sandwich is one named case of a
middleman; and the number the page leads with is the one the join actually found — a
round-trip share that the sponsor's own activity ranking is built on.

**2026-09-19.** The first cut of the join called four things on USDT/DGAI (PancakeSwap v3, BSC)
sandwiches. They were two wallets washing around each other — each selling and buying back
for exactly the quote it received, take zero. A sandwich now requires `take > 0`; a same-wallet
return with nothing extracted is a round-trip whether or not other makers printed between the
legs. The regression test is named for it.

---

## Endpoints used — all keyless, four load-bearing

| # | Endpoint | Role |
|---|---|---|
| 1 | `/public-api/v1/dex/tokens/transactions` | **the engine** — `ma`, `h`, `lgid`, `tp`, `a0`, `a1`, `tx`, `en`, `t0a`, `t1a` per swap; `lastId` cursor |
| 2 | `/public-api/v1/dex/token/pools` | pool address, venue, `liqUsd` — labels each `(en, t0a, t1a)` group, counts merged fee tiers |
| 3 | `/public-api/v1/dex/security/detail` | `extra.buyTax` / `extra.sellTax` — a transfer tax is never counted as a middleman |
| 4 | `/public-api/v4/dex/pairs/quotes/latest` | `24h_no_of_buys` + `24h_no_of_sells` — how much of a day the window covers |
| 5 | `/public-api/v4/dex/spot-pairs/latest` | the hero rule — #1 pair by `no_of_transactions_24h`, per chain |
| 6 | `/public-api/v1/dex/platform/list` | explorer URL templates for the transaction links |

**Why only CoinMarketCap.** The join needs the maker address, the block, the log index, the
side and both amounts, per swap, for every pool of a token across a chain, keyless, with a
cursor. The maker address is what lets "the same wallet on both sides" be *counted* rather than
suspected; the log index is what makes "between" exact inside a block instead of a timestamp
heuristic. CMC has no mempool view and no MEV labels — and the product does not need them,
because a middleman has to print. Remove CoinMarketCap and you would need a multi-chain swap
indexer with maker attribution, a per-DEX pool registry, a fee-on-transfer simulator, a second
aggregator for pair counts and an explorer map — five systems — to recompute what eight keyless
pages return. Where the API got in the way is in **[FEEDBACK.md](FEEDBACK.md)**: eight dated
findings, from the missing CORS header to `q` being rounded on Uniswap v4 rows.

---

## Run it

```bash
git clone https://github.com/edycutjong/middleman.git && cd middleman
python3 scripts/middleman.py                                   # the hero by rule, live, keyless
python3 scripts/middleman.py --address 0x… --symbol X --pages 8 --json x.json   # any token; --platform bsc|solana
python3 scripts/middleman.py --watchlist                       # SHIB · PEPE · UNI

make setup && make test                                        # 133 offline tests
make test-live                                                 # 6 tests against the real contract, keyless
python3 scripts/verify_tape.py                                 # every receipt re-derived from its tape, offline
make bench                                                     # the engine over the committed tape, p50/p95
node scripts/serve.js                                          # the page + the keyless proxy on :8101
```

The library is importable — six pure functions, stdlib only:

```python
from middleman import tape, detect, cost, recommend

prints, meta = tape.pull("ethereum", "0xbd965230588eaa536de6aa45e8ebbc01638535e0", pages=8)
for key, rows in detect.group(prints).items():
    rt, sw, organic = detect.middlemen(rows)
    row = cost.pool_row(key, rows, rt, sw, organic)
```

---

## Tests and proof

| | |
|---|---|
| Tests | **139** — 133 offline, 6 live; each regression named for the defect it pins |
| Property-based | `middlemen()` over **1,000 generated blocks**, 0 violations of its own definition |
| Parity | the browser engine (`site/middleman.js`) vs the Python engine, every pool row of every committed tape |
| Re-derivation | `scripts/verify_tape.py` — every published number from its tape, offline; `make check` fails on drift |
| Drift gate | `scripts/render_site.py --check` — the committed page is what the receipts render, or the build fails |
| Live contract | `tests/test_live.py` asserts the real row shape: fields present, `h`/`lgid` parse as ints, `a1/a0` computable, `t0a` is the queried token |
| Benchmarks | engine p50 **3.3 ms** / 800 prints (n=200) · one keyless page p50 **1.5 s**, p95 16.4 s — one iteration sat through the throttle backoff |

---

## Honest limitations

- **The window is the last 800 prints, not 24 hours** — 3.6 h on the hero, 20 h on SHIB. The
  span is on every row; the receipt carries the window's share of the pool's 24 h count.
- **Uniswap v3 fee tiers of one pair merge** — the feed carries no pool address; a row marked ×n
  is n pools sharing (venue, base, quote).
- **Quote-to-fill is a realised, fee-inclusive print-to-print move** — p90 sits near 60 bps on
  every busy 0.30 % pool because consecutive opposite-side prints straddle the fee twice. It is
  used comparatively, across pools of one token in one window, where the bias is shared.
- **A round-trip is a shape, not a verdict** — same wallet, same block, opposite sides,
  size-matched. The rows and the definition are printed; nobody is labelled.
- **The anonymous tier throttles per IP**, reports it as 500 as often as 429, and sends no
  `Retry-After`. The tool backs off 15 / 30 / 60 s and exits 75 when the quota is spent.
- **The deployed paste box shares one IP** across every visitor. The page renders from committed
  receipts, the proxy caches 60 s, and the CLI is the primary live path.

---

## Links

| | |
|---|---|
| **Judge guide** | [JUDGE.md](JUDGE.md) |
| **Demo + receipts** | [DEMO.md](DEMO.md) · [`docs/proof/`](docs/proof/) |
| **How it works** | [ARCHITECTURE.md](ARCHITECTURE.md) · [docs/METHOD.md](docs/METHOD.md) |
| **API feedback** | [FEEDBACK.md](FEEDBACK.md) |
| **Live page** | [middleman-cmc.vercel.app](https://middleman-cmc.vercel.app) · [/evidence](https://middleman-cmc.vercel.app/evidence) |
| **Event** | [Build with CMC: API Hackathon](https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail) — Markets and Trading Tools |

MIT · [@edycutjong](https://x.com/edycutjong)
