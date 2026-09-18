# Feedback on the CoinMarketCap API

Written for the CMC product team, who asked for exactly this. Every item below was hit while
building [Middleman](README.md) against the live API on 2026-09-18 and 2026-09-19 — nothing
here is speculative, and each finding carries the date it was observed, the call that produced
it, and the evidence file in this repository.

The headline: **`/v1/dex/tokens/transactions` is the most useful endpoint in the DEX
catalogue** — the maker address and the log index on every swap, keyless, on nine venues
across three chains, are what let this project *count* who stood between two prints instead
of guessing. Six of the eight items below are about making it easier to build on, not about
what it returns.

---

## 1. `/public-api` sends three CORS headers and omits the only one browsers gate on

**Observed 2026-09-19 · every `/public-api` endpoint · severity: high**

A keyless `200` carries `Access-Control-Allow-Headers`, `Access-Control-Allow-Methods` and
`Access-Control-Max-Age: 600` — and not `Access-Control-Allow-Origin`. Sent with an `Origin`
header, the response is identical (`docs/proof/spike.json → cors`). The preflight succeeds,
the request goes out, the body arrives, and the browser discards it.

**Why it matters:** the keyless surface reads as an invitation to build web tools on it, and
every one of them needs a server-side hop whose only job is to copy the response and add one
header — which also puts every visitor of that tool behind a single IP against a per-IP
anonymous rate limit (item 2). This project's [`api/swaps.js`](api/swaps.js) is 60 lines that
exist only because of this. `Access-Control-Allow-Origin: *` on `/public-api` would delete it
and every proxy like it. The data is already public and unauthenticated.

## 2. The anonymous tier throttles per IP with no `Retry-After` and no published quota

**Observed 2026-09-18 and 2026-09-19 · severity: high**

Eight pages of one token from one IP trip the limit about once — HTTP 429, `error_code 1022`,
*"You've reached the limit for anonymous access"* — and under load the same condition arrives
as HTTP 500 *"The system is busy"*. Neither carries `Retry-After` or any `X-RateLimit-*`
header, and a successful response reports `credit_count: 1` against an account that does not
exist. A 15 s backoff recovers the short throttle; the long horizon (roughly 3,700 calls per
IP per day, measured on a sibling project) does not recover for hours.

**Why it matters:** a keyless client cannot budget what it cannot see. This tool backs off
15 s / 30 s / 60 s, exits 75 (`EX_TEMPFAIL`) when the quota is spent, and prints the two ways
through — but a `Retry-After` on the 429 and a published per-minute / per-day quota would let
every keyless integration behave correctly without guesswork. Reporting the throttle as a 500
also teaches clients to do the wrong thing: give up on a recoverable condition, or hammer a
service that is not actually failing.

## 3. `h`, `lgid`, `ts`, `txId` and `tc` are numbers delivered as strings

**Observed 2026-09-18 · `/v1/dex/tokens/transactions` · severity: medium**

Block height and log index are the two fields that place a swap inside the chain, and both
arrive as JSON strings. A client that sorts without casting gets `"99" > "1000"` and a silently
wrong block order — every "between" in a sandwich detector is then wrong, with no error. The
amounts (`a0`, `a1`, `v`, `q`) are numbers on the same row.

**What would fix it:** deliver `h` and `lgid` as integers, or document that they are strings
next to the field list. This project casts on read and has a regression test named for the trap
(`test_block_and_log_index_are_sorted_as_integers_not_as_the_strings_they_arrive_as`).

## 4. `q` is rounded to two significant figures, or zero, on Uniswap v4 rows

**Observed 2026-09-19 · PEPE, 400 rows · severity: medium**

`q` equals `a1 / a0` to six significant figures on 374 of 400 rows. On the 26 others — 22 on
Uniswap v4, 4 on Uniswap v3 — it reads `1.5e-09` against a computed `1.481e-09` (1.3 % off),
or `0` outright (`docs/proof/spike.json → tapes.PEPE.fields.q_mismatch_by_venue`). Nothing on
the row says which kind of `q` it is.

**Why it matters:** `q` is the field a price-per-print consumer reaches for first. A 1–2 %
error on one venue's rows would be invisible in a chart and fatal in a basis-point comparison
between pools. This project never reads `q`; it divides `a1 / a0` itself. Either populate `q`
at full precision on every venue or drop it from the rows where it is not.

## 5. `en` is null on ~4 % of Ethereum rows, so those prints cannot be attributed to a pool

**Observed 2026-09-19 · PEPE, 16 of 400 rows (`ex: true`) · severity: medium**

The row has a factory address `f` and both contracts, so the pool exists; the venue name is
just missing. The feed carries no pool address, so `(en, t0a, t1a)` is the only way to
reconstruct a pool from a per-token feed — and a null `en` puts those prints in a bucket the
page has to label *unattributed*.

**What would fix it:** a pool address on every swap row. It would also resolve item 6.

## 6. Uniswap v3 fee tiers of one pair are indistinguishable on the feed

**Observed 2026-09-18 · SHIB, UNI, LINK · severity: medium**

Three Uniswap v3 pools of one pair (0.05 %, 0.30 %, 1 %) return rows with the same `en`,
`t0a` and `t1a`. `/v1/dex/token/pools` lists them as three pools with three addresses, but
nothing on the swap row says which one printed. This project merges them and marks the row
×3; a fill can only be attributed to the pair, not the tier. A `pool` field on the swap row —
the same `addr` that `token/pools` returns — would make the per-pool numbers exact.

## 7. `spot-pairs/latest` ignores `limit`; `pairs/quotes/latest` puts the `aux` counts on the row

**Observed 2026-09-19 · severity: low (two documentation notes)**

- `/v4/dex/spot-pairs/latest?…&limit=1` returns 100 rows (`docs/proof/spike.json →
  hero_rule.rows_returned_for_limit_1`). The sort works — `sort=no_of_transactions_24h` is
  how this project picks its hero by rule — but a caller who wanted one row pays for a hundred.
- On `/v4/dex/pairs/quotes/latest` with `aux=24h_no_of_buys,24h_no_of_sells,num_transactions_24h`,
  every other number lives inside `quote[0]` and the three aux counts land on the **row**
  object, where `quote[0]` shows them as `null`. Found by printing both levels, not by reading
  the docs.

## 8. Slugs and casing differ between neighbouring endpoints

**Observed 2026-09-18 and 2026-09-19 · severity: low**

The swap feed and `token/pools` take `platform=ethereum|bsc|solana`; `security/detail` takes
`platformName`; `pairs/quotes/latest` takes `network_slug=ethereum` and `network_slug=solana`
but rejects `network_slug=bsc` (*"not supported"*) and wants `network_id=14`;
`spot-pairs/latest` requires a `dex_slug` and takes `network_id`. `security/detail` returns
its `data` as a one-element list and puts the tax under `extra.buyTax` in camelCase; `token/pools`
returns `liqUsd` as a string; `limit` above 100 on the swap feed is HTTP 400 rather than a
clamp. Each was found from the error message. One parameter name and one casing across the
DEX family — or a table of them on one page — would save every integrator a morning.

---

## What is genuinely excellent, and worth protecting

`/v1/dex/tokens/transactions` returns, per swap, keyless: the **maker address** `ma`, the
**block** `h`, the **log index** `lgid`, the side, both amounts and the transaction hash. That
row shape is the whole engine of this project. The maker address is what lets "the same wallet
on both sides of a block" be **counted** rather than suspected; the log index is what makes
"between" exact inside a block instead of a timestamp heuristic. We are not aware of another
market-data API that publishes both on every swap with no key.

It matters more than it sounds because the API has **no mempool view and no MEV labels** — and
it does not need them. A middleman has to print, and with `ma` and `lgid` on the row the print
order alone names them: 45 round-trips by 14 wallets and 2 sandwiches by one, in 8,000 prints,
each one two rows a reader can divide by hand. **The constraint is the discovery.** Items 3–6
are about keeping that row trustworthy; items 1 and 2 are about letting people reach it.

---

*Filed by [@edycutjong](https://x.com/edycutjong) for the Build with CMC: API Hackathon.
Reproduce any item above with `python3 scripts/spike.py` or `python3 scripts/middleman.py` —
no key required.*
