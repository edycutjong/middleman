# Contributing

## Run it in 30 seconds — no key, no signup, no install

```bash
git clone https://github.com/edycutjong/middleman.git && cd middleman
python3 scripts/middleman.py
```

`scripts/middleman.py` is stdlib-only and calls CoinMarketCap's keyless `/public-api` surface,
so what you see is a live API response, not a fixture. With no flags it asks CMC's own ranking
which Uniswap v2 pair on Ethereum is busiest and names the middleman on that token's last 800
prints.

## Development

```bash
make setup           # dev deps only: pytest, pytest-cov, ruff, mypy, hypothesis, pip-audit
make lint            # ruff check + format check
make lint-fix        # ruff --fix + format, in place
make typecheck       # mypy over middleman/, scripts/ and tests/
make test            # 251 offline tests, no internet
make test-coverage   # the same, branch coverage of the engine gated at 95%
make test-live       # 6 tests against the real CoinMarketCap contract, keyless
make demo            # the judged capability, live, no key
make verify          # every committed receipt re-derived from its tape, offline
make site            # re-render /, /evidence and /judge from docs/proof/*.json
make serve           # site/ + api/ on http://localhost:8101, the way Vercel routes them
make bench           # p50/p95 of the engine over the committed tape (deterministic)
make bench-live      # p50/p95 of the real keyless fetch
make audit           # pip-audit + gitleaks over the full history
make check           # refuse to ship a placeholder, a stale count, or a page that drifted
make ci              # lint + typecheck + test-coverage + audit + check
```

## The one rule that matters here

**Never mock the judged capability.** The point of this project is that the numbers come from
real prints. If a test needs determinism, replay one of the committed tapes in `data/` (capture
fresh ones with `make seed`) — but the default path, `make demo`, the deployed page's paste box
and CI's `live-api` job must always hit the real API. A pull request that puts the join behind
a `MOCK=` or `OFFLINE=` flag will be closed.

`scripts/bench.py --replay` is the one sanctioned offline path, and it is labelled a replay
everywhere it appears. It times the engine, not the product.

## Tests

Three categories carry more weight than coverage here, and PRs are expected to keep them:

- **Regression tests are named after the defect they pin** —
  `test_a_return_that_extracted_nothing_is_a_round_trip_even_around_another_makers_print`, not
  `test_detect_7`. The test list is meant to read as a changelog of real bugs.
- **`middlemen()` is verified by property, not by example** (`tests/test_property.py`, 1,000
  generated blocks). If you change the join, its invariants must still hold across the generated
  input space: every print is a leg or organic and never both, every round-trip is the same
  wallet's next print on the other side at a matched size, every sandwich has one to four
  victims who printed in the first leg's direction, and the attacker came out ahead.
- **The proxy's boundary is proven, not described** (`tests/test_proxy_boundary.py`).
  `api/swaps.js` may reach exactly one keyless CoinMarketCap URL and may never forward a
  caller's credential. Touching it means keeping those assertions green.

Every number a judge reads is gated: `tests/test_published_counts.py` fails when a surface
publishes a test count the suite does not have, `render_site.py --check` fails when a page is
not what its receipts render, and `verify_tape.py` fails when a receipt does not re-derive from
its tape.

## Commits

Conventional commits (`feat:`, `fix:`, `perf:`, `docs:`, `chore:`, `test:`, `ci:`, `build:`).
Small and iterative. `release.yml` derives the version from these, so the prefix decides the bump.

## Reporting bugs / requesting features

Open an issue using the provided templates. For a wrong number, paste the command, the printed
table and the receipt JSON if you wrote one — the receipt carries every URL and body hash.
