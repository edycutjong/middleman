"""The four labelling endpoints, against the response shapes verified live 2026-09-19."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from middleman import enrich, tape  # noqa: E402

MOTO = "0xbd965230588eaa536de6aa45e8ebbc01638535e0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"


def _ok(body, url="u"):
    return {
        "ok": True,
        "url": url,
        "status": 200,
        "utc": "t",
        "sha256": "h",
        "credit_count": 1,
        "body": body,
    }


def _fail(error="HTTP 429", throttled=True):
    return {
        "ok": False,
        "url": "u",
        "status": 429,
        "utc": "t",
        "error": error,
        "throttled": throttled,
    }


def _serve(monkeypatch, call):
    seen = []

    def fake(path, quiet=False, **params):
        seen.append((path, params))
        return call

    monkeypatch.setattr(tape, "get", fake)
    return seen


# ── token/pools ──────────────────────────────────────────────────────────────────────────────


def test_token_pools_reads_liquidity_from_a_string_and_both_contracts(monkeypatch):
    body = {
        "data": [
            {
                "addr": "0xpool",
                "exn": "Uniswap v2",
                "liqUsd": "959262.365332372836124317",
                "t0": {"addr": MOTO, "sym": "MOTO"},
                "t1": {"addr": WETH, "sym": "WETH"},
                "fa": "0xfactory",
            }
        ]
    }
    seen = _serve(monkeypatch, _ok(body))
    pools, receipt = enrich.token_pools("ethereum", MOTO)
    assert pools == [
        {
            "addr": "0xpool",
            "venue": "Uniswap v2",
            "liq_usd": 959262.365332372836124317,
            "base_address": MOTO,
            "quote_symbol": "WETH",
            "quote_address": WETH,
            "factory": "0xfactory",
        }
    ]
    assert seen[0][0] == "/v1/dex/token/pools" and seen[0][1]["platform"] == "ethereum"
    assert "body" not in receipt


def test_a_pool_that_lists_the_token_as_t1_still_labels_its_row():
    """MOTO/USDC on Uniswap v2 lists USDC as t0 and MOTO as t1 (live 2026-09-19)."""
    pools = [
        {
            "addr": "0xusdc",
            "venue": "Uniswap v2",
            "liq_usd": 38897.6,
            "base_address": USDC.upper(),
            "quote_address": MOTO,
        },
    ]
    rows = [{"key": ["Uniswap v2", MOTO, USDC]}]
    enrich.label_pools(rows, pools, MOTO)
    assert (
        rows[0]["addr"] == "0xusdc"
        and rows[0]["liq_usd"] == 38897.6
        and rows[0]["pools_merged"] == 1
    )


def test_merged_fee_tiers_are_counted_and_their_liquidity_summed_with_the_deepest_address():
    pools = [
        {
            "addr": "0x05",
            "venue": "Uniswap v3 (Ethereum)",
            "liq_usd": 100.0,
            "base_address": MOTO,
            "quote_address": WETH,
        },
        {
            "addr": "0x30",
            "venue": "Uniswap v3 (Ethereum)",
            "liq_usd": 900.0,
            "base_address": MOTO,
            "quote_address": WETH,
        },
        {
            "addr": "0xv2",
            "venue": "Uniswap v2",
            "liq_usd": 5.0,
            "base_address": MOTO,
            "quote_address": WETH,
        },
    ]
    rows = [{"key": ["Uniswap v3 (Ethereum)", MOTO, WETH]}, {"key": ["Uniswap v2", MOTO, USDC]}]
    enrich.label_pools(rows, pools, MOTO)
    assert (
        rows[0]["pools_merged"] == 2 and rows[0]["addr"] == "0x30" and rows[0]["liq_usd"] == 1000.0
    )
    assert rows[1]["pools_merged"] == 0 and rows[1]["addr"] is None and rows[1]["liq_usd"] is None


def test_a_failed_pools_call_labels_nothing_and_keeps_the_receipt(monkeypatch):
    _serve(monkeypatch, _fail())
    pools, receipt = enrich.token_pools("ethereum", MOTO)
    assert pools is None and receipt["ok"] is False
    rows = [{"key": ["Uniswap v2", MOTO, WETH]}]
    enrich.label_pools(rows, pools, MOTO)
    assert rows[0]["addr"] is None


# ── security/detail ──────────────────────────────────────────────────────────────────────────


def test_security_reads_camel_case_taxes_from_a_list_wrapped_data_block(monkeypatch):
    body = {"data": [{"securityLevel": "safe", "extra": {"buyTax": "2.5", "sellTax": "0.0"}}]}
    seen = _serve(monkeypatch, _ok(body))
    taxes, _ = enrich.security("ethereum", MOTO)
    assert taxes == {"buy_tax": 2.5, "sell_tax": 0.0, "level": "safe"}
    assert seen[0][1]["platformName"] == "ethereum"


def test_security_tolerates_a_dict_data_block_and_a_missing_extra(monkeypatch):
    _serve(monkeypatch, _ok({"data": {"securityLevel": "unknown"}}))
    taxes, _ = enrich.security("ethereum", MOTO)
    assert taxes == {"buy_tax": None, "sell_tax": None, "level": "unknown"}


def test_security_failure_is_none_not_a_crash(monkeypatch):
    _serve(monkeypatch, _fail())
    assert enrich.security("ethereum", MOTO)[0] is None


# ── pairs/quotes/latest ──────────────────────────────────────────────────────────────────────


def test_pair_quotes_reads_the_aux_counts_from_the_row_not_the_quote_block(monkeypatch):
    body = {
        "data": [
            {
                "num_transactions_24h": 4848,
                "24h_no_of_buys": 2621,
                "24h_no_of_sells": 2227,
                "quote": [
                    {
                        "liquidity": 958936.4,
                        "volume_24h": 3.78e6,
                        "price": 0.0036,
                        "24h_no_of_buys": None,
                    }
                ],
            }
        ]
    }
    seen = _serve(monkeypatch, _ok(body))
    cov, _ = enrich.pair_quotes("ethereum", "0xpool")
    assert (
        cov["num_transactions_24h"] == 4848 and cov["buys_24h"] == 2621 and cov["sells_24h"] == 2227
    )
    assert cov["liquidity_usd"] == 958936.4
    assert seen[0][1]["network_slug"] == "ethereum" and "aux" in seen[0][1]


def test_bsc_is_addressed_by_network_id_because_its_slug_is_not_supported(monkeypatch):
    seen = _serve(monkeypatch, _ok({"data": []}))
    cov, _ = enrich.pair_quotes("bsc", "0xpool")
    assert cov is None and seen[0][1]["network_id"] == 14 and "network_slug" not in seen[0][1]


def test_pair_quotes_refuses_an_unknown_platform_or_a_missing_pool_without_a_call(monkeypatch):
    seen = _serve(monkeypatch, _ok({"data": []}))
    assert enrich.pair_quotes("moonchain", "0xpool")[0] is None
    assert enrich.pair_quotes("ethereum", None)[0] is None
    assert seen == []


# ── the hero rule ────────────────────────────────────────────────────────────────────────────


def test_the_hero_rule_takes_the_first_row_of_cmcs_own_ranking_and_notes_limit_is_ignored(
    monkeypatch,
):
    body = {
        "data": [
            {
                "name": "MOTO/WETH",
                "base_asset_symbol": "MOTO",
                "base_asset_contract_address": MOTO,
                "quote_asset_symbol": "WETH",
                "contract_address": "0xpool",
                "dex_slug": "uniswap-v2",
            },
            {"name": "UNI/WETH"},
        ]
    }
    seen = _serve(monkeypatch, _ok(body))
    hero, _ = enrich.hero_pair()
    assert hero["address"] == MOTO and hero["pool"] == "0xpool" and hero["rows_returned"] == 2
    assert seen[0][1]["sort"] == "no_of_transactions_24h" and seen[0][1]["dex_slug"] == "uniswap-v2"
    assert hero["rule"] == enrich.HERO_RULE


def test_the_hero_rule_returns_none_when_the_ranking_is_empty_or_throttled(monkeypatch):
    _serve(monkeypatch, _ok({"data": []}))
    assert enrich.hero_pair()[0] is None
    _serve(monkeypatch, _fail())
    hero, receipt = enrich.hero_pair()
    assert hero is None and receipt["throttled"]


# ── platform/list ────────────────────────────────────────────────────────────────────────────


def test_explorer_links_come_from_the_platform_lists_template(monkeypatch):
    body = {
        "data": [{"id": 1, "n": "Ethereum", "txuf": "https://etherscan.io/tx/%s", "addrUrl": "a"}]
    }
    _serve(monkeypatch, _ok(body))
    table, _ = enrich.platforms()
    assert enrich.explorer_tx("ethereum", "0xabc", table) == "https://etherscan.io/tx/0xabc"
    assert enrich.explorer_tx("bsc", "0xabc", table) is None
    assert enrich.explorer_tx("ethereum", None, table) is None
    _serve(monkeypatch, _fail())
    assert enrich.platforms()[0] is None
