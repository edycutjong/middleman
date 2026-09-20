# Demo — a real run, with its receipt

Everything below is a transcript of actual runs against CoinMarketCap's live API on
**2026-09-18**. No fixtures, no flags, no key. Re-run it yourself in one command; the numbers
will differ, because they come from the market rather than from this file — and on this pair
they moved by the hour, which is the point.

## Reproduce

```bash
git clone https://github.com/edycutjong/middleman.git && cd middleman
python3 scripts/middleman.py
```

That is the whole thing. No `pip install`, no `.env`, no signup — the engine is stdlib-only and
every endpoint it calls is on CoinMarketCap's keyless `/public-api` surface. With no flags the
tool asks CMC's own ranking which Uniswap v2 pair on Ethereum has the most transactions in the
last 24 h, pulls that token's last 800 prints, and names the middleman. Any token, any of the
three chains:

```bash
python3 scripts/middleman.py --address 0xbd965230588eaa536de6aa45e8ebbc01638535e0 --symbol MOTO --pages 8 --json moto.json
python3 scripts/middleman.py --address 0x95ad61b0a150d79219dcf64e1e6cc01f0b64c4ce --symbol SHIB --platform ethereum
python3 scripts/middleman.py --watchlist            # SHIB · PEPE · UNI, three pages each
```

**There is no offline flag on this path, deliberately.** The one replay mode in the repository
(`scripts/bench.py --replay`) times the engine over a committed tape and is labelled a replay
everywhere it appears; it is not the product. `scripts/verify_tape.py` re-derives every
published number from the committed tapes offline — that is the judge's check, not the demo.

**~10 s is the clean-path time** for 800 prints and three labelling calls. The endpoint is
CoinMarketCap's shared anonymous tier, rate-limited per IP. If it is throttling when you run,
the script backs off (15 s, 30 s, 60 s) and says so; if your IP's quota is exhausted outright,
it exits **75** (`EX_TEMPFAIL`) with a message naming the two ways through — wait a few
minutes, or export a free key from [coinmarketcap.com/api](https://coinmarketcap.com/api) as
`CMC_API_KEY`, which moves the identical call to the keyed host. The key is an escape hatch,
never a requirement: every receipt below was taken with every CMC variable unset, and a keyed
run announces itself on its first line and in its receipt, so it can never pass as one of these.

## Receipt 1 — the capture behind the page, 2026-09-18T22:36:19Z

`scripts/seed.py`, keyless. The token was chosen by the published rule — *the base token of the
pair CoinMarketCap ranks #1 on Ethereum Uniswap v2 by 24 h transactions at capture time* — and
it was MOTO/WETH. The page at [middleman.edycu.dev](https://middleman.edycu.dev) is
rendered from this receipt; `python3 scripts/verify_tape.py` re-derives it from
[`data/tape_moto.json`](data/tape_moto.json) with the network unplugged.

| | |
|---|---|
| **Wall clock** | **8.6 s** — 8 pages of 100 prints plus 3 labelling calls, no backoff fired |
| **Token** | MOTO on Ethereum, `0xbd965230588eaa536de6aa45e8ebbc01638535e0` — #1 Uniswap v2 pair by CMC's own 24 h ranking |
| **Prints** | **800** · blocks 26006339–26007416 · **3.6 h** · 15.7 % of the pair's 4,899 transactions that day |
| **API calls** | 11 · every one HTTP 200 |
| **Credits used** | **0** — `/public-api`, no key exists to charge |
| **Credentials** | none. `CMC_API_KEY`, `COINMARKETCAP_API_KEY`, `CMC_PRO_API_KEY` explicitly unset |
| **Endpoint** | `https://pro-api.coinmarketcap.com/public-api/v1/dex/tokens/transactions` |
| **Cursor** | `data.lastId` on the response envelope · prints keyed by `(tx, lgid)` |
| **Raw receipt** | [`docs/proof/moto.json`](docs/proof/moto.json) — every URL, status, body hash; the rows behind the example; the rule |

```
MOTO · ethereum · 800 prints · 3.6 h · blocks 26006339–26007416 · captured 2026-09-18T22:36:19Z · keyless

  66.2% of Uniswap v2 / WETH volume is 3 wallet(s) buying back what they just sold (29 round-trips, same transaction)

  pool                         prints organic  round-trips                sandw  q→fill p50 / p90     tax     liq
  ----------------------------------------------------------------------------------------------------------------
  Uniswap v2 / WETH               770     712  29 · 3 wallet(s) · 66.2%       0  15.5 / 60.9 bps      0/0   $956k  ◀ route
  Uniswap v2 / USDC                17      17  —                              0  66.5 / 137.8 bps     0/0    $39k
  Uniswap v2 / USDT                13      13  —                              0  71.1 / 135.2 bps     0/0    $34k

  ▶ route via Uniswap v2 / WETH · cap slippage at 0.65 %   (organic p90 60.9 bps, 1 candidate pool(s))
    rule: lowest organic p90 quote-to-fill among pools with ≥ 50 organic prints
    coverage: this window is 16% of the routed pool's 24h transactions (4899: 2654 buys / 2245 sells)

  block 26006339 — raw rows (round-trip)
    lgid   202  0x9c97c0a6a0…  buy  a0       561,202.9606  a1       0.699926  a1/a0 1.2472e-06
    lgid   209  0xc9160fdab1…  sell a0       842,991.8538  a1       1.043025  a1/a0 1.2373e-06  ◀ leg
    lgid   218  0xc9160fdab1…  buy  a0       829,640.6520  a1       1.032594  a1/a0 1.2446e-06  ◀ leg
    lgid   225  0xdd64c9d73e…  sell a0       774,494.6589  a1       0.958588  a1/a0 1.2377e-06
    lgid   234  0xdd64c9d73e…  buy  a0       762,222.4667  a1       0.949003  a1/a0 1.2450e-06
    leg 1  lgid 209  0xc9160fdab187f2e55567b760d88a87ae7fe56d95  sell  a1/a0 = 1.0430246602456774 / 842991.8537715519 = 1.237289133434893e-06
    leg 2  lgid 218  0xc9160fdab187f2e55567b760d88a87ae7fe56d95  buy  a1/a0 = 1.0325944136432206 / 829640.6520318444 = 1.2446285161103536e-06
    same wallet · same block 26006339 · same tx · |Δa0| / a0 = 0.0158 ≤ 0.05 → round-trip
```

### Read the MOTO row the way a trader would

CoinMarketCap ranks this pair **#1 on Uniswap v2 by transactions**. Of the $192,275 that
printed in the window, **$127,254 — 66.2 % — is three wallets selling and buying back the same
size inside one transaction**, 29 times. `0xc9160fda…` alone: sell 842,991 MOTO, buy 829,640
MOTO back, 1.6 % apart, same block, same tx hash. The pair is at the top of the ranking
*because* of them.

The cost number is wrong until they are taken out. Print-to-print, a fill on this pool lands
**55.3 bps** behind the print before it if you believe the whole tape, and **15.5 bps** once the
58 round-trip legs are removed. A trader reading the raw tape would size a cap three and a half
times too loose.

### Check it by hand

Two rows, same `ma`, same `tx`. Divide `a1` by `a0` for each leg: 1.2373e-06 and 1.2446e-06 —
the price each leg paid, in WETH per MOTO. `|Δa0| / a0` = |829,640 − 842,991| / 842,991 = 0.0158.
That is the whole definition. The receipt's `pools[0].example.rows` carries these rows verbatim
from the API; the tape carries all 800.

## Receipt 2 — the zero-flag command, 2026-09-18T23:00:18Z

The same run, 24 minutes later, as the first line of this file has it — with `--json
docs/proof/live_run.json` appended so the receipt was kept (the bare command prints the same
table and writes nothing). **The number moved** — the three wallets had gone quiet, one of
them still printing — which is what a live measurement does and a fixture cannot. Receipt:
[`docs/proof/live_run.json`](docs/proof/live_run.json).

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

## Receipt 3 — the same command, and a clean window, 2026-09-19T00:28:45Z

Run again the next morning as the R10 gate of the engineering pass — keyless, from this tree,
with `--json docs/proof/live_run_quiet.json` so the receipt was kept. **Zero round-trips.** The
three wallets were gone, every one of the 800 prints was organic, and the tool said so on the
line the headline usually occupies — then routed and capped from the pool's own p90, which is
what the fallback is for. Receipt: [`docs/proof/live_run_quiet.json`](docs/proof/live_run_quiet.json).

```
middleman 0.1.0 — keyless, live

hero rule: the base token of the #1 Ethereum Uniswap v2 pair by 24h transactions at capture time
  → MOTO/WETH  0xbd965230588eaa536de6aa45e8ebbc01638535e0

MOTO · ethereum · 800 prints · 4.17 h · blocks 26006729–26007978 · captured 2026-09-19T00:28:46Z · keyless

  no middleman found in this window — every print organic; the cap is the pool's own p90

  pool                         prints organic  round-trips                sandw  q→fill p50 / p90     tax     liq
  ----------------------------------------------------------------------------------------------------------------
  Uniswap v2 / WETH               779     779  —                              0  7.4 / 60.7 bps         —   $943k  ◀ route
  Uniswap v2 / USDC                12      12  —                              0  46.2 / 98.0 bps        —    $37k
  Uniswap v2 / USDT                 8       8  —                              0  47.3 / 115.9 bps       —    $34k
  Uniswap v4 (Ethereum) / ETH       1       1  —                              0  — / — bps              —    $109

  ▶ route via Uniswap v2 / WETH · cap slippage at 0.65 %   (organic p90 60.7 bps, 1 candidate pool(s))
    rule: lowest organic p90 quote-to-fill among pools with ≥ 50 organic prints
    coverage: this window is 15% of the routed pool's 24h transactions (5236: 2855 buys / 2381 sells)

  block 26006729 — raw rows (organic)
    lgid   538  0xf06e3c5535…  buy  a0        10,248.8270  a1       0.014111  a1/a0 1.3769e-06
    lgid   556  0x8965d2b3ef…  buy  a0           232.9306  a1       0.000321  a1/a0 1.3770e-06  ◀ leg
    previous print  lgid 538  buy  a1/a0 = 1.3768550773349123e-06
    this print      lgid 556  buy  a1/a0 = 1.376964652537947e-06
    q/q_prev − 1 = 0.8 bps adverse

wrote docs/proof/live_run_quiet.json  (11.0s wall clock, 0 credits — keyless)
```

| | |
|---|---|
| **Wall clock** | **11.0 s** — 8 keyless pages + 3 labelling calls, no backoff fired |
| **Prints** | **800** · blocks 26006729–26007978 · **4.17 h** · 15% of the pair's 5,236 transactions that day |
| **API calls** | 11 · every one HTTP 200 |
| **Credits used** | **0** — keyless; `CMC_API_KEY` unset |
| **Round-trips** | **0** · sandwiches 0 · organic p50 **7.4 bps**, p90 60.7 |

Four windows on the same pair, one night: **80.0 %** of volume round-tripped at 22:12 UTC
([`docs/proof/spike.json`](docs/proof/spike.json), the day-1 spike), **66.2 %** at 22:36,
**27.5 %** at 23:00, **0 %** at 00:28. The wallets come and go; the ranking that put the pair
at #1 does not — and a tool that can print *zero* on its own headline is the one whose non-zero
you can believe.

## The census — ten tokens, whatever they said

`scripts/seed.py` ran the same engine over the hero on each of three chains (by the same rule
on PancakeSwap v2 and Raydium) and seven pinned Ethereum tokens. Every receipt is committed,
every number re-derives from its tape. [`docs/proof/census.json`](docs/proof/census.json):

| Token · chain | Prints | Span | Pools | Round-trips | Sandwiches | Route · cap |
|---|---|---|---|---|---|---|
| **MOTO** · ethereum (hero by rule) | 800 | 3.6 h | 3 | **29 · 3 wallets · 66.2 % of volume** | 0 | Uniswap v2 / WETH · 0.65 % |
| SHIB · ethereum | 800 | 20.3 h | 18 | 0 | 0 | ShibaSwap / WETH · 0.65 % |
| PEPE · ethereum | 800 | 17.2 h | 14 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| UNI · ethereum | 800 | 1.8 h | 19 | 0 | **1** | Uniswap v3 / WETH · 0.20 % |
| LINK · ethereum | 800 | 6.1 h | 22 | 0 | **1** | Uniswap v4 / ETH · 0.05 % |
| AAVE · ethereum | 800 | 5.9 h | 17 | 0 | 0 | Uniswap v3 / WETH · 0.15 % |
| Mog · ethereum | 800 | 22.9 h | 5 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| SPX · ethereum | 800 | 20.7 h | 8 | 0 | 0 | Uniswap v2 / WETH · 0.65 % |
| USDT · bsc (hero by rule) | 800 | 0.01 h | 172 | 13 | 0 | PancakeSwap v4 / KII · 0.05 % |
| USDC · solana (hero by rule) | 800 | 0.01 h | 167 | 3 | 0 | Tessera V / SOL · 0.05 % |

**8,000 prints · 445 pools · 2 sandwiches · 45 round-trips by 14 wallets.** The widest sibling
spread on Ethereum: LINK, **22.9×** — 0.6 bps median quote-to-fill on Uniswap v4 / ETH against
14.2 on Uniswap v3 / USDC, same token, same hours.

### The two sandwiches are real, and they are the same wallet

Both on Uniswap v3 / WETH, both `0xae2fc483527b8ef99eb5d9b44875f005ba1fae13`, three separate
transactions inside one block each time:

```
UNI  · block 26007128
  lgid 371  0xae2fc483…  sell  379.4305 UNI  for 1.302930 WETH   tx 0xc9073de1…   ◀ leg
  lgid 393  0x05854d0c…  sell   25.5021 UNI  for 0.086685 WETH   tx 0xf0161be3…   ◀ victim
  lgid 409  0xae2fc483…  buy   379.4305 UNI  for 1.302570 WETH   tx 0x420c25c8…   ◀ leg
  take: 1.302930 − 1.302570 = 0.000361 WETH

LINK · block 26006427
  lgid 187  0xae2fc483…  sell  140.2809 LINK for 0.655987 WETH   tx 0x316bbc5a…   ◀ leg
  lgid 197  0xf5f3ef37…  sell  171.4012 LINK for 0.799861 WETH   tx 0x1b449f4a…   ◀ victim
  lgid 212  0xae2fc483…  buy   140.2809 LINK for 0.655155 WETH   tx 0x53676342…   ◀ leg
  take: 0.655987 − 0.655155 = 0.000832 WETH
```

Sell ahead of a seller, buy back behind them, pocket the difference — a dollar and two
dollars respectively. Two in 8,000 prints. **The sandwich rate this project was built to
headline is 0.025 %**, and the README says so.

## Benchmarks

```bash
make bench        # deterministic: the engine over the committed hero tape, no network
make bench-live   # the real keyless fetch
```

Fetch and engine are timed **separately**, because averaging them would hide the only
interesting fact: the product's own work is milliseconds, and everything a judge waits for is
network — or the anonymous tier's backoff.

| Measurement | n | p50 | p95 |
|---|---|---|---|
| Engine over 800 prints, replay ([`bench_replay.json`](docs/proof/bench_replay.json)) | 200 | **3.3 ms** | 3.7 ms |
| One keyless page, live ([`bench_live.json`](docs/proof/bench_live.json)) | 8 | **1,513 ms** | 16,399 ms |
| Engine, live (100 prints) | 8 | 0.9 ms | 5.4 ms |

That live p95 of 16.4 s is not a typo and it is not smoothed away: **one of the eight iterations
hit CMC's anonymous throttle and sat through a 15-second backoff.** That is the honest cost of a
keyless demo, and it is why the backoff exists.

## Tests

| | Count |
|---|---|
| Total tests | **145** (139 offline, 6 live) |
| Regression tests, each named for the defect it pins | 39 |
| Property-based verification of the join | **1,000 generated blocks, 0 violations** |
| JavaScript ↔ Python parity | every committed tape, every pool row |
| Offline re-derivation of every published number | `python3 scripts/verify_tape.py` |

```bash
make test         # 139 offline tests, no internet
make test-live    # 6 tests against the real CMC contract, keyless
```

The property test generates blocks of prints and checks that `middlemen()` never violates its
own definition: every print is either a leg or organic and never both, every round-trip is the
same wallet's next print on the other side at a matched size, every sandwich has one to four
victims who all printed in the first leg's direction and are still in the organic sample, and
the attacker came out ahead. The live tests assert the **external** contract — that a real row
carries `h, lgid, ma, tp, a0, a1, tx, t0a, t1a`, that `h` and `lgid` are strings that parse as
integers, that `a1/a0` is computable on every row, and that `t0a` is the queried token — so
they fail if CoinMarketCap changes the shape, not if this code does.

## Honest limitations

- **The window is the last 800 prints, not 24 hours.** 3.6 h on MOTO, 20 h on SHIB. The span is
  on every row, and the receipt carries the window's share of the pool's 24 h transactions.
- **Uniswap v3 fee tiers of one pair merge.** The feed carries no pool address; pools are
  recovered from `(en, t0a, t1a)`, and a row marked ×n is n pools sharing that key.
- **Quote-to-fill is a realised print-to-print move, fee-inclusive.** On a 0.30 % pool two
  consecutive opposite-side prints straddle the fee twice, so p90 sits near 60 bps on every busy
  v2 pool. It is used comparatively across pools of one token, where that bias is shared — which
  is also why the routing rule prefers the 0.05 % tiers when they are deep enough.
- **A round-trip is a shape, not a verdict.** Same wallet, same block, opposite sides,
  size-matched. Tapes show the rows and the definition; nobody is labelled.
- **The anonymous tier throttles per IP** and reports it as HTTP 500 as often as 429, with no
  `Retry-After`. The tool backs off and says so; an exhausted quota exits 75. Filed in
  [FEEDBACK.md](FEEDBACK.md).
- **The deployed paste box shares one IP.** Ten judges pasting at once can 429 each other; the
  page renders from committed receipts, the proxy caches for 60 s, and the CLI is the primary
  live path.
