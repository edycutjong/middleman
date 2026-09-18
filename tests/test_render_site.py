"""The pages are what the receipts render — and nothing else can reach them."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

import render_site  # noqa: E402


def test_the_committed_site_is_what_the_committed_receipts_render(capsys):
    """The drift gate: a number typed into site/ by hand, or a receipt changed without a
    re-render, fails here and in `make check`."""
    assert render_site.main(["--check"]) == 0
    assert "site/ is what docs/proof" in capsys.readouterr().out


def test_an_unfilled_slot_stops_the_render_rather_than_shipping_the_braces():
    with pytest.raises(SystemExit) as e:
        render_site.render("<p>{{hero.share}} and {{missing.slot}}</p>", {"hero.share": "66.2%"})
    assert "missing.slot" in str(e.value.code)


def test_the_front_page_carries_the_receipt_the_headline_came_from():
    census, platforms, receipts = render_site.load_all()
    page = render_site.front_page(census, platforms, receipts)
    hero = render_site.hero_receipt(census, receipts)
    assert (
        hero["symbol"] in page
        and hero["captured_utc"].replace("T", " ").replace("Z", " UTC") in page
    )
    assert "/public-api/v1/dex/tokens/transactions" in page
    first_hash = next(c["sha256"] for c in hero["calls"] if c.get("ok"))
    assert first_hash in page  # the page hash a judge can compare with the tape's
    assert "▶ route via" in page or "no route" in page
    assert 'id="receipts"' in page and "</script>" in page
    embedded = json.loads(
        page.split('<script id="receipts" type="application/json">')[1].split("</script>")[0]
    )
    assert [r["symbol"] for r in embedded["receipts"]] == [
        r["symbol"] for r in receipts if r["platform"] == "ethereum"
    ]
    assert all("calls" not in r for r in embedded["receipts"])  # the call lists live on /evidence


def test_the_headline_falls_through_from_round_trips_to_the_spread_to_nothing():
    census, platforms, receipts = render_site.load_all()
    hero = render_site.hero_receipt(census, receipts)
    fired = render_site.hero_ctx(hero, census)
    assert fired["kind"] in ("middle", "spread", "none")
    clean = dict(census, hero=dict(census["hero"], fired="sibling-pool spread"))
    assert render_site.hero_ctx(hero, clean)["kind"] == "spread"
    empty = dict(census, hero=dict(census["hero"], fired="none"), widest_spread=None)
    assert render_site.hero_ctx(hero, empty)["kind"] == "none"


def test_the_rows_panel_shows_the_pool_the_headline_is_about():
    census, platforms, receipts = render_site.load_all()
    link = next(r for r in receipts if r["symbol"] == "LINK")
    pool = render_site.hero_pool(link)
    assert (
        pool["sandwiches"]["count"] >= 1
        or pool["round_trips"]["pairs"] >= 1
        or pool["key"] == link["decision"]["pool"]
    )
    ctx = render_site.example_ctx(link, platforms)
    assert pool["venue"] in ctx["title"]


def test_the_evidence_page_lists_every_call_with_its_hash_and_status():
    census, platforms, receipts = render_site.load_all()
    page = render_site.evidence_page(census, platforms, receipts)
    total = sum(len(r["calls"]) for r in receipts)
    assert f"{total} requests" in page
    for r in receipts:
        for c in r["calls"]:
            if c.get("ok"):
                assert c["sha256"] in page
    assert "python3 scripts/verify_tape.py" in page
    for endpoint, _ in render_site.ENDPOINTS:
        assert endpoint in page


def test_the_og_image_is_exactly_the_card_size_platforms_resample_to():
    head = render_site.OG_IMAGE.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n"
    import struct

    w, h = struct.unpack(">II", head[16:24])
    assert (w, h) == (1200, 630)
