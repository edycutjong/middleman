.PHONY: help setup lint test test-live bench bench-live demo seed site serve verify audit check ci all

help:  ## show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n",$$1,$$2}'

setup:  ## install dev deps (the product itself needs none)
	python3 -m pip install -r requirements-dev.txt

lint:  ## ruff check + format check
	ruff check . && ruff format --check .

test:  ## pytest, offline only (no internet)
	pytest -q -m "not live"

test-live:  ## the live tests — hit the real CoinMarketCap API, keyless
	pytest -q -m live

demo:  ## the judged capability, live, zero config, no key
	python3 scripts/middleman.py

seed:  ## re-capture the tapes and receipts from the live API by the published rule
	python3 scripts/seed.py

bench:  ## deterministic benchmark against the committed tape, p50/p95
	python3 scripts/bench.py --replay --iterations 200

bench-live:  ## benchmark the real keyless fetch, p50/p95
	python3 scripts/bench.py --iterations 8

verify:  ## re-derive every published number from the committed tapes, offline
	python3 scripts/verify_tape.py

site:  ## re-render site/ from docs/proof/*.json
	python3 scripts/render_site.py

serve:  ## serve site/ + api/ locally the way Vercel routes them (port 8101)
	node scripts/serve.js

audit:  ## dependency + secret audit
	pip-audit -r requirements-dev.txt || true
	gitleaks detect --no-banner --redact || true

check:  ## refuse to ship a placeholder, or a page that drifted from its receipts
	python3 scripts/check_submission_readiness.py
	python3 scripts/render_site.py --check
	python3 scripts/verify_tape.py

ci: lint test check  ## everything CI runs, offline
all: ci bench  ## ci plus the deterministic benchmark
