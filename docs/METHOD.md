# Method — the definitions, the invariant, the exclusions

Enough to reimplement the join from scratch. Every symbol is a field of one row of
CoinMarketCap's `/v1/dex/tokens/transactions` response; nothing else enters.

## Input

One token, one chain, the last *N* prints (default 800 = 8 pages × 100, the endpoint's cap).
A print is a swap row: `h` block height, `lgid` log index, `ma` maker address, `tp` side
(`buy` | `sell`, from the token's point of view), `a0` base amount (the token), `a1` quote
amount, `tx` transaction hash, `en` venue name, `t0a` / `t1a` the two contracts, `ts`
milliseconds, `v` USD.

`h`, `lgid` and `ts` arrive as **strings** and are cast to integers before anything is
compared. `(tx, lgid)` is the only unique key across pages. The next-page cursor is
`data.lastId` on the response envelope.

## Definitions

**Order.** Sort by `(int(h), int(lgid))` ascending — the print's exact position inside the
chain. A row whose `h` or `lgid` does not parse is dropped from the join and counted in the
receipt as `unplaceable`.

**Pool.** `(en or "unattributed", t0a, t1a)`. The feed is per token and carries no pool
address; the venue name and the two contracts identify a pool. Uniswap v3 fee tiers of one
pair share a key and merge; the row reports how many pools `token/pools` lists under it.

**Price of a print.** `q = a1 / a0` — quote units per base unit, the effective price that
print paid. Computed, never read from the feed's `q`, which is rounded to two significant
figures or zero on Uniswap v4 rows.

**Legs.** Two prints `a`, `b` of one pool can be the two legs of a middleman when
`a.ma == b.ma`, `int(a.h) == int(b.h)`, `a.tp != b.tp`, and `|b.a0 − a.a0| / a.a0 ≤ 0.05`.

**The join.** Walk the pool's prints in order. For print `a` by wallet A, find A's **next**
print `b` in the same block. If `a`, `b` are legs, A stood on both sides of the block, and the
prints between them decide the shape:

- **Sandwich (A-B-A)** — between the legs there are 1 to 4 prints, every one by another maker,
  every one in `a`'s direction, none of them already a leg of an earlier match, and A came out
  ahead: `take > 0`, where `take = b.a1 − a.a1` if `a` is a buy and `a.a1 − b.a1` if it is a
  sell. The prints between are the **victims**.
- **Round-trip (A-A)** — anything else: no print between (the same wallet selling and buying
  back inside one transaction), or prints between that are mixed, or a return that extracted
  nothing. Two wallets washing around each other — B sell · C sell · B buy · C buy — are two
  round-trips, not sandwiches; each is recorded with the number of prints between its legs and
  whether both legs share a `tx`.

A leg belongs to at most one match. Victims are never consumed.

**Organic.** Every print that is neither leg of a match. Victims stay organic — their fills
are real, and what they paid is the question.

**Quote-to-fill.** For consecutive organic prints `p`, `r` of one pool, the adverse-signed
basis points of `r`'s price against `p`'s:

```
buy:   (q_r / q_p − 1) × 10 000
sell:  (1 − q_r / q_p) × 10 000
```

Positive means `r` paid more (or received less) than the print before it. The first organic
print of a pool has no quote and is skipped. The **naive** series is the same over all prints,
legs included.

**Percentiles.** Nearest-rank: `rank = ceil(p / 100 × n)`, clamped to `[1, n]`; the value at
that rank of the sorted series. Every p50 and p90 is a real observation, never an
interpolation — and `ceil`, not `round`, because Python rounds half to even and JavaScript
half away from zero, and the two engines disagreed on a 16-print pool until it was `ceil`.

**Row.** Per pool: prints, organic prints, distinct makers, USD volume, span in hours,
round-trips (pairs, wallets, share of prints, share of volume, share inside one `tx`),
sandwiches (count, wallets, victims, take), organic p50 / p90, naive p50 / p90, and the
example block a judge re-derives by hand.

**Route.** Among pools with at least 50 organic prints in the window, the lowest organic p90.
**Cap.** That p90, rounded **up** to the next 0.05 %, never below 0.05 %.

## The invariant

An AMM pool's price moves only when someone prints in it. So the print before yours is the
quote you saw, and the distance to the price you paid is what stood between the two: a
middleman's legs, or the pool's own thinness. Quote-to-fill measures that distance; the join
names the legs.

## The exclusions — what is measured, and what is not claimed

1. **The window is the last *N* prints, not a day.** Hours on a busy pair, most of a day on a
   quiet one. The receipt states the span and the window's share of the pool's 24 h count.
2. **Quote-to-fill is realised and fee-inclusive.** It includes the previous print's own
   footprint and both prints' fees; on a 0.30 % pool consecutive opposite-side prints straddle
   the fee twice, which is why p90 sits near 60 bps on every deep v2 pool. It is a comparison
   between pools of one token in one window, where the bias is shared, not a marginal
   impact curve.
3. **A round-trip is a shape.** Same wallet, same block, opposite sides, size-matched. Nothing
   here says *why* — a wash, a hedge, an arbitrage leg that happened to return. The rows and
   the definition are printed; the reader names it.
4. **A maker is an address, not an entity.** One entity can span wallets (the share is a
   floor); a router can pool many users into one maker (it inflates). The join is at address
   level, no more.
5. **A wallet's legs across two pools are two different pools' prints.** The join is within a
   pool; a triangular route that touches two pools is not matched, by design — the question is
   who stood between two prints in *this* pool.
6. **Merged fee tiers.** A Uniswap v3 row marked ×3 is three pools' prints in one series;
   quote-to-fill across tiers is a realised move across the pair, not one tier.
7. **Sandwiches under 0.025 %.** Across 8,000 prints on ten tokens and three chains the join
   found two. That is the finding, stated as measured; nothing in the method inflates it.

## Reproducing the numbers

```bash
python3 scripts/verify_tape.py     # every docs/proof/<sym>.json from its data/tape_<sym>.json, offline
python3 scripts/middleman.py       # today's numbers, live, keyless
```
