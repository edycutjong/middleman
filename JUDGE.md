# For judges

Everything you need in one page. No setup, no key, no account.
Built on the CoinMarketCap API for the Build with CMC: API Hackathon — **Markets and Trading
Tools** track.

## The claim

**A DEX trader sees a quote and a fill and cannot tell what stood between them. Middleman
orders a token's real prints by block and log index, joins them on the maker address, and
names it: the wallet on both sides of a block, or the pool itself. Then it says where to
route and what slippage cap to set.**

## The 30-second path

The judged capability is a command-line tool, and that is the whole install:

```bash
git clone https://github.com/edycutjong/middleman.git && cd middleman
python3 scripts/middleman.py
```

No `pip install` (stdlib only), no `.env`, no API key, no signup. With no flags the tool asks
CoinMarketCap's own ranking which Uniswap v2 pair on Ethereum is busiest, pulls that token's
last 800 prints, and prints the table, the route line and the raw rows of the first middleman
it found — with the arithmetic. About ten seconds. If your IP is being throttled by the
anonymous tier the run says so and backs off; an exhausted quota exits 75 with the way through
(wait, or export a free key as `CMC_API_KEY` — an escape hatch, never a requirement).

The page at **[middleman.edycu.dev](https://middleman.edycu.dev)** shows the same
table for the same token, rendered from a committed run, with the raw rows one click away and
every request behind it on **[/evidence](https://middleman.edycu.dev/evidence)**. Paste
any token into its box and the browser runs the same engine, live, through a keyless proxy.
This guide is also served at **[/judge](https://middleman.edycu.dev/judge)** — rendered
from the same receipts, no key, no cookie, no session — if you would rather not clone at all.

1. **Read the headline.** *66.2 % of the #1 Uniswap v2 pair's volume is 3 wallets buying back
   what they just sold, in the same transaction.* CoinMarketCap ranks the pair first by
   transactions; the join shows why.
2. **Read the table.** One row per pool: prints, organic prints, round-trips, sandwiches, the
   basis points an organic fill pays against the print before it (p50 / p90), tax, liquidity.
   The green bar is the route; orange is a middleman.
3. **Check two rows by hand.** Same `ma`, same block, opposite sides, `a0` within 5 %. Divide
   `a1` by `a0` — that is the price each leg paid. The panel does it inline; the JSON is verbatim.
4. **Run `python3 scripts/verify_tape.py`.** Every number on the page re-derives from the
   committed tapes with the network unplugged. Then run the bare command for today's.

## Receipt — the capture behind the page, 2026-09-18T22:36:19Z

| | |
|---|---|
| Wall clock | **8.6 s** — 8 keyless pages + 3 labelling calls, no backoff fired |
| Prints | **800** — MOTO on Ethereum, chosen by rule (#1 Uniswap v2 pair by 24 h transactions) |
| API calls | 11, every one HTTP 200 |
| **Credits used** | **0** — keyless `/public-api`; no key exists to charge |
| Credentials | none; every CMC variable explicitly unset |
| Round-trips | **29 · 3 wallets · 66.2 % of the pool's volume** ($127,254 of $192,275), all inside one transaction |
| Sandwiches | 0 on this pair · **2 in 8,000 prints** across the ten-token census, both by one wallet |
| Quote-to-fill | organic **15.5 bps** median, p90 60.9 — the raw tape says 55.3 |
| Route | Uniswap v2 / WETH · **cap slippage at 0.65 %** |
| Tests | **257** (251 offline, 6 live) · property-based: 1,000 generated blocks, 0 violations · JS ↔ Python parity on every tape · the proxy's boundary pinned by test |
| Engine latency | p50 **3.3 ms** per 800 prints (p95 3.7 ms, n=200) |
| Live fetch latency | p50 **1.5 s** per page (p95 16.4 s — one iteration sat through the throttle backoff) |
| Raw receipts | [`docs/proof/moto.json`](docs/proof/moto.json) · [`census.json`](docs/proof/census.json) · [`live_run.json`](docs/proof/live_run.json) · [`spike.json`](docs/proof/spike.json) · [`bench_live.json`](docs/proof/bench_live.json) · [`bench_replay.json`](docs/proof/bench_replay.json) |

The same command 24 minutes later measured **27.5 %** — the wallets had gone quiet; the next
morning the window was **clean**, zero round-trips, and the tool said so. A number that moves
with the market is the proof it is measured, not asserted. Two days later the rule picked a
different pair and the join found **17 sandwiches** in one window. All four transcripts are in
[DEMO.md](DEMO.md).

## Reproduce

```bash
python3 scripts/middleman.py                                   # the hero by rule, live, keyless
python3 scripts/middleman.py --address 0xbd965230588eaa536de6aa45e8ebbc01638535e0 --symbol MOTO --pages 8 --json moto.json
python3 scripts/verify_tape.py                                 # every receipt vs its tape, offline
make test                                                      # 251 offline tests
make test-live                                                 # 6 tests against the real contract
make bench                                                     # the engine over the committed tape
node scripts/serve.js                                          # the page + proxy on :8101
```

**CI / deterministic replay — not the product:** `make bench` times the engine over
`data/tape_moto.json`, a recording made by `scripts/seed.py`. Nothing on the judged path reads
a tape; `scripts/middleman.py` always fetches live and has no offline flag.

## Why only CoinMarketCap

The join needs, per swap, the **maker address, the block, the log index, the side and both
amounts** — for every pool of a token across a chain, keyless, with a cursor. That row shape is
what `/v1/dex/tokens/transactions` returns, and nowhere else is it published without an
indexer. The maker address is what lets "the same wallet on both sides" be counted instead of
suspected; the log index is what makes "between" exact inside a block. CMC has no mempool view
and no MEV labels, and the product does not need them: the middleman has to print.

Six endpoints, all keyless, four load-bearing: `tokens/transactions` (the engine),
`token/pools`, `security/detail`, `pairs/quotes/latest` (the labels), `spot-pairs/latest`
(the hero rule), `platform/list` (the explorer links). Remove CoinMarketCap and you would need a
multi-chain swap indexer with maker attribution, a per-DEX pool registry, a fee-on-transfer
simulator, a second aggregator for pair counts and an explorer map — five systems — to
recompute what eight keyless pages return.

## What we got wrong

This project was decided as *the sandwich rate per pool*. The day-1 spike found **zero**
same-block sandwiches in 1,200 prints on the busiest pair; the ten-token census found two in
8,000. The headline changed before the build, not the caveat after: the engine is unchanged,
the sandwich is one named case of a middleman, and the number on the page is the one the join
actually found — a round-trip share that the sponsor's own activity ranking is built on. Two
days later the same command found 17 sandwiches in one window on a different pair — small on
average is not small everywhere. Both retractions are dated in the README.

## Honest limitations

- **A run measures the last 800 prints, not 24 hours** — 3.6 h on the hero, 20 h on SHIB. The
  span is on every row; the receipt carries the window's share of the pool's 24 h count.
- **Uniswap v3 fee tiers of one pair merge** — the feed carries no pool address. A row marked ×n
  is n pools; the number is per pair, not per tier.
- **Quote-to-fill is fee-inclusive and realised** — p90 sits near 60 bps on every busy 0.30 %
  pool because consecutive opposite-side prints straddle the fee twice. Used comparatively.
- **A round-trip is a shape, not a verdict.** The rows and the definition are printed; nobody
  is labelled.
- **The anonymous tier throttles per IP** — the paste box on the deployed page shares one; the
  page renders from committed receipts and the CLI is the primary live path.

## Links

| | |
|---|---|
| **Run it** | [DEMO.md](DEMO.md) — four real transcripts with receipts |
| **How it works** | [ARCHITECTURE.md](ARCHITECTURE.md) — derived from the code · [docs/METHOD.md](docs/METHOD.md) — the definitions |
| **API feedback for CMC** | [FEEDBACK.md](FEEDBACK.md) — eight dated, evidenced findings |
| **The engine** | [`middleman/`](middleman/) — six stdlib modules · [`scripts/middleman.py`](scripts/middleman.py) — the door |
| **The tests** | [`tests/`](tests/) — 257 tests, each regression named for the defect it pins |
| **Live page** | [middleman.edycu.dev](https://middleman.edycu.dev) · [/judge](https://middleman.edycu.dev/judge) · [/evidence](https://middleman.edycu.dev/evidence) |
