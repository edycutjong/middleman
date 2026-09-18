# Middleman

**Who stands between your quote and your fill, per pool — from real DEX prints, keyless.**

Pulls the last 800 swaps of a token from CoinMarketCap's `/v1/dex/tokens/transactions`, orders
them by block and log index, joins them on the maker address, and names every wallet that printed
on both sides of a block: round-trips, sandwiches. Then it prices what an organic fill actually
paid in each pool and tells you where to route and what slippage cap to set.

Built for the Build with CMC: API Hackathon (DoraHacks) — Markets and Trading Tools track.

```bash
python3 scripts/middleman.py        # live, keyless, no install
```

Work in progress — see [DEMO.md](DEMO.md) once the first live run is committed.
