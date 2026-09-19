.PHONY: help setup lint lint-fix typecheck test test-coverage test-live bench bench-live demo seed site serve verify audit security-scan check ci all

help:  ## show targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-14s %s\n",$$1,$$2}'

setup:  ## install dev deps (the product itself needs none)
	python3 -m pip install -r requirements-dev.txt

# ── Code quality ─────────────────────────────────────────────────────────────
lint:  ## ruff check + format check
	ruff check . && ruff format --check .

lint-fix:  ## ruff --fix + format, in place
	ruff check --fix . && ruff format .

typecheck:  ## mypy over middleman/, scripts/ and tests/ (config in pyproject.toml)
	mypy

test:  ## pytest, offline only (no internet)
	pytest -q -m "not live"

test-coverage:  ## offline tests, branch coverage of the engine (middleman/) gated at 95%
	pytest -q -m "not live" --cov=middleman --cov-report=term-missing --cov-report=xml --cov-fail-under=95

test-live:  ## the live tests — hit the real CoinMarketCap API, keyless
	pytest -q -m live

# ── The product ──────────────────────────────────────────────────────────────
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

site:  ## re-render site/ (/, /evidence, /judge) from docs/proof/*.json
	python3 scripts/render_site.py

serve:  ## serve site/ + api/ locally the way Vercel routes them (port 8101)
	node scripts/serve.js

# ── Security ─────────────────────────────────────────────────────────────────
audit:  ## dependency CVEs (pip-audit) + secrets in the working tree and history (gitleaks)
	@echo "=== pip-audit (dependency CVEs) ==="
	pip-audit -r requirements-dev.txt || true
	@echo "=== gitleaks (secrets, full history) ==="
	gitleaks detect --no-banner --redact || true

security-scan: audit  ## alias — the name /enhance-project's harness table uses

# ── Gates ────────────────────────────────────────────────────────────────────
check:  ## refuse to ship a placeholder, a stale count, or a page that drifted from its receipts
	python3 scripts/check_submission_readiness.py
	python3 scripts/render_site.py --check
	python3 scripts/verify_tape.py

ci: lint typecheck test-coverage audit check  ## everything CI runs, offline
all: ci bench  ## ci plus the deterministic benchmark
