#!/usr/bin/env python3
"""Render site/index.html, site/evidence.html, site/judge.html and site/pitch/index.html
from the committed receipts.

    python3 scripts/render_site.py            # write site/
    python3 scripts/render_site.py --check    # exit 1 if what is on disk is not this render

Every number on any of the four pages comes from docs/proof/*.json — real keyless runs recorded by
scripts/seed.py. The templates in scripts/site_templates/ use {{slot}} tokens and the render
fails if any slot is left unfilled, so a placeholder can never reach the committed HTML and
a number can never be typed in by hand. The HTML under site/ is generated output: edit the
template or the receipt, never the page.

The front page is rendered once, server-side, for the hero token, so it shows the reveal
with JavaScript off and makes zero requests. The same receipts are embedded as JSON so the
token buttons switch the table client-side, and the paste box runs the JavaScript port of
the engine (site/middleman.js) on rows fetched through /api/swaps.
"""

import hashlib
import html
import json
import re
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD))

from middleman import __version__, enrich, recommend  # noqa: E402

TEMPLATES = BUILD / "scripts" / "site_templates"
PROOF = BUILD / "docs" / "proof"
SITE = BUILD / "site"

REPO = "https://github.com/edycutjong/middleman"
REPO_SHORT = "github.com/edycutjong/middleman"
# Every off-site link says so: the ↗ mark and the screen-reader text, pasted after the link's
# own text. The rendered rows, the receipt and the runs emit it; site/middleman.js carries the
# same string for the rows it re-renders on a token switch or a live fetch.
EXT = (
    '<span class="arrow arrow-ext" aria-hidden="true">↗</span>'
    '<span class="sr-only"> (opens in a new tab)</span>'
)
# The canonical host. middleman.edycu.dev is a custom domain on the same Vercel project as
# middleman-cmc.vercel.app (DNS added 2026-09-20); both serve this build, the custom domain is
# the one every og:url and canonical names, and the paste box is same-origin on either.
SITE_URL = "https://middleman.edycu.dev"
SITE_SHORT = "middleman.edycu.dev"
# The version stamp on the deck's cover and in the landing page's footer: the package's own
# declared version — the string the CLI prints on its first line — so the page, the deck and
# `python3 scripts/middleman.py` agree. Not `git describe`: the CI job that gates site/ against
# its templates clones shallow with no tags, and a render that depended on tags would drift.
DECK_VERSION = f"v{__version__}"
# The counts /judge publishes. tests/test_published_counts.py fails if they drift from the suite.
TESTS_TOTAL, TESTS_OFFLINE, TESTS_LIVE = 145, 139, 6
PROPERTY_CASES = 1000
EVENT = "https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail"
AUTHOR = "Edy Cu"
X_HANDLE = "@edycutjong"
OG_IMAGE = SITE / "assets" / "og-image.png"
TAGLINE = "Who stands between your quote and your fill, per pool."

ENDPOINTS = [
    (
        "/v1/dex/tokens/transactions",
        "the engine — ma, h, lgid, tp, a0, a1, tx, en, t0a, t1a per swap",
    ),
    ("/v1/dex/token/pools", "pool address, venue, liqUsd — labels each (en, t0a, t1a) group"),
    ("/v1/dex/security/detail", "extra.buyTax / extra.sellTax — a transfer tax is not a middleman"),
    ("/v4/dex/pairs/quotes/latest", "24h buy / sell counts — how much of a day the window covers"),
    ("/v4/dex/spot-pairs/latest", "the hero rule — #1 pair by 24h transactions, per chain"),
    ("/v1/dex/platform/list", "explorer URL templates for the transaction links"),
]


def esc(s):
    return html.escape(str(s), quote=True)


def short(addr, n=6):
    a = str(addr or "")
    return a[:n] + "…" + a[-4:] if len(a) > n + 4 else a


def utc_short(ts):
    return str(ts).replace("T", " ").replace("Z", " UTC")


def utc_hhmm(ts):
    return str(ts)[11:16]


def usd(v):
    if v is None:
        return "—"
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}k"
    return f"${v:.0f}"


def bps(v):
    return "—" if v is None else f"{v:.1f}"


def price(row):
    try:
        a0, a1 = float(row["a0"]), float(row["a1"])
        return a1 / a0 if a0 > 0 else None
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return None


def load_all():
    census = json.loads((PROOF / "census.json").read_text())
    platforms = json.loads((PROOF / "platforms.json").read_text())["platforms"]
    receipts = []
    for row in census["rows"]:
        path = BUILD / row["file"]
        if path.exists():
            receipts.append(json.loads(path.read_text()))
    return census, platforms, receipts


def hero_receipt(census, receipts):
    sym = census["hero"]["symbol"]
    return next(r for r in receipts if r["symbol"] == sym and r["platform"] == "ethereum")


# ── the front page ───────────────────────────────────────────────────────────


def hero_ctx(r, census):
    """The headline: the round-trip share when the rule fired on it, the spread otherwise."""
    fired = census["hero"]["fired"]
    top = r["pools"][0]
    routed = next((p for p in r["pools"] if p["key"] == r["decision"]["pool"]), top)
    cov = r.get("coverage") or {}
    coverage = (
        f"{cov['window_share_of_24h']:.0%}"
        if cov.get("window_share_of_24h")
        else "an unknown share"
    )
    if fired == "round-trip share":
        hp = census["hero"]["pool"]
        pool = next(
            p for p in r["pools"] if p["venue"] == hp["venue"] and p["quote"] == hp["quote"]
        )
        rt = pool["round_trips"]
        share = rt["share_volume"]
        same_tx = (rt.get("same_tx_share") or 0) >= 0.5
        naive, organic = pool["naive"]["p50_bps"], pool["q2f"]["p50_bps"]
        return {
            "kind": "middle",
            "share_num": f"{share * 100:.1f}",
            "share_text": f"{share * 100:.1f}%",
            "share_int": f"{share * 100:.0f}",
            "share": f"{share * 100:.1f}%",
            "wallets_n": len(rt["wallets"]),
            "claim": (
                f"of {pool['venue']} / {pool['quote']} volume is <em>{len(rt['wallets'])} wallets</em> "
                f"buying back what they just sold{', in the same transaction' if same_tx else ''}."
            ),
            "support": (
                f"{rt['pairs']} round-trips · {pool['sandwiches']['count']} sandwiches in {pool['n']} prints. "
                f"Take the legs out and an organic fill here pays <b>{bps(organic)} bps</b> median; "
                f"the raw tape says {bps(naive)}."
            ),
            "symbol": r["symbol"],
            "quote": pool["quote"],
            "prints": r["window"]["prints"],
            "span": r["window"]["span_hours"],
            "coverage": coverage,
            "address": r["address"],
        }
    spread = census.get("widest_spread")
    if spread:
        return {
            "kind": "spread",
            "share_num": f"{spread['ratio']:.1f}",
            "share_text": f"{spread['ratio']:.1f}×",
            "share_int": f"{spread['ratio']:.0f}",
            "share": f"{spread['ratio']:.1f}×",
            "wallets_n": 0,
            "claim": (
                f"more per fill in <em>{esc(spread['high']['pool'])}</em> than in "
                f"{esc(spread['low']['pool'])} — same token, same hour."
            ),
            "support": (
                f"No round-trips and no sandwiches on the hero pair today — the middleman is the pool "
                f"itself. {esc(spread['symbol'])}: {bps(spread['low']['p50_bps'])} vs "
                f"{bps(spread['high']['p50_bps'])} bps median quote-to-fill."
            ),
            "symbol": r["symbol"],
            "quote": routed["quote"],
            "prints": r["window"]["prints"],
            "span": r["window"]["span_hours"],
            "coverage": coverage,
            "address": r["address"],
        }
    return {
        "kind": "none",
        "share_num": "0",
        "share_text": "0",
        "share_int": "0",
        "share": "0%",
        "wallets_n": 0,
        "claim": "middlemen found in this window — every print organic; the cap is the pool's own p90.",
        "support": f"{r['window']['prints']} prints, every one organic.",
        "symbol": r["symbol"],
        "quote": routed["quote"],
        "prints": r["window"]["prints"],
        "span": r["window"]["span_hours"],
        "coverage": coverage,
        "address": r["address"],
    }


def lead_ctx(r, census, hero, pool):
    """The first viewport: the title tags, the two-line h1 with the count-up, the lede, and
    the block drawn from the receipt's own example rows. Word-light on purpose — a judge
    decides in one viewport whether to scroll, and the rows are one scroll down."""
    kind = hero["kind"]
    venue = census["hero"]["pool"]["venue"] if kind == "middle" else pool["venue"]
    platform = r["platform"].title()
    if kind == "middle":
        n = hero["wallets_n"]
        line1 = f"The #1 {esc(venue)} pair on {esc(platform)}, by transactions."
        line2 = (
            f'<span class="big" data-count="{hero["share_num"]}">{hero["share_text"]}</span> of it is '
            f"{n} wallet{'s' if n != 1 else ''} trading with themselves."
        )
        title = (
            f"Middleman — {hero['share_int']}% of the #1 {venue} pair is "
            f"{n} wallets trading with themselves"
        )
        og_desc = (
            f"{hero['share']} of the #1 {venue} pair's volume was {n} wallets buying back what they "
            f"just sold. From real DEX prints, keyless."
        )
        og_alt = (
            f"Middleman — {hero['share']} of {r['symbol']}/{hero['quote']} volume is {n} wallets "
            f"buying back what they just sold, in the same transaction. Two blue prints, one orange hairpin."
        )
    elif kind == "spread":
        sp = census["widest_spread"]
        line1 = "Same token, same hours, two pools."
        line2 = (
            f'<span class="big" data-count="{hero["share_num"]}">{hero["share_text"]}</span> more per fill '
            f"in one of them."
        )
        title = f"Middleman — {hero['share_int']}× more per fill in one {esc(sp['symbol'])} pool than its sibling"
        og_desc = f"{hero['share']} more per fill in one pool than its sibling — same token, same hours. Per-pool, from real DEX prints, keyless."
        og_alt = f"Middleman — {hero['share']} between two pools of one token. Two blue prints, one orange hairpin."
    else:
        line1 = "No middleman in this window."
        line2 = f'<span class="big" data-count="0">0</span> of {hero["prints"]} prints had a wallet on both sides.'
        title = "Middleman — who stands between your quote and your fill, per pool"
        og_desc = "Every print organic in this window; the cap is the pool's own p90. Per-pool, from real DEX prints, keyless."
        og_alt = "Middleman — a window with no middleman. Blue prints, no hairpin."
    description = (
        f"{TAGLINE} From real prints on the keyless CoinMarketCap API. "
        f"{r['symbol']}: {hero['share']} of volume is {hero['wallets_n']} wallets round-tripping."
        if kind == "middle"
        else f"{TAGLINE} From real prints on the keyless CoinMarketCap API. {r['symbol']}, {hero['prints']} prints, {hero['span']} h."
    )
    viz, key = hero_viz(r, pool)
    tx_pages = len([c for c in r["calls"] if "tokens/transactions" in str(c.get("url", ""))])
    return {
        "title": esc(title),
        "description": esc(description),
        "og_description": esc(og_desc),
        "og_alt": esc(og_alt),
        "line1": line1,
        "line2": line2,
        "lede": TAGLINE,
        "date": str(r["captured_utc"])[:10],
        "captured": utc_short(r["captured_utc"]),
        "viz": viz,
        "viz_key": key,
        "viz_foot": (
            f"{esc(r['symbol'])} · {esc(r['platform'])} · {r['window']['prints']} prints · "
            f"{tx_pages} pages · {r['wall_s']} s"
        ),
        "organic_p90": bps(pool["q2f"]["p90_bps"]),
    }


def hero_viz(r, pool):
    """The block, drawn from the receipt: one bar per print in the example block, its length
    the print's base amount; the two legs of the first middleman are the orange ones, joined
    by the hairpin. No text inside the SVG — the key beneath it carries the numbers, so the
    first viewport stays a picture and the words stay countable."""
    ex = pool.get("example") or {}
    rows = (ex.get("rows") or [])[:6]
    legs = [lg for lg in (ex.get("highlight") or []) if any(x.get("lgid") == lg for x in rows)]
    victims = set(ex.get("victims") or [])
    kind = ex.get("kind", "organic")
    sym = esc(r["symbol"])
    if not rows:
        svg = (
            '<svg class="block" viewBox="0 0 1200 120" role="img" aria-label="No example block in this window" '
            'xmlns="http://www.w3.org/2000/svg"><line class="rail" x1="40" y1="20" x2="40" y2="100"/></svg>'
        )
        return svg, f"<span><i></i>{sym}: a single print in the window — nothing to compare</span>"
    a0s = [abs(float(x.get("a0") or 0)) for x in rows]
    mx = max(a0s) or 1.0
    top, rowh, x0, barmax = 16, 44, 70, 1090
    height = top * 2 + rowh * len(rows)
    leg_rows = [x for x in rows if x.get("lgid") in legs]
    label = {
        "round-trip": (
            f"Block {esc(ex.get('h'))}: {len(rows)} prints of {sym}. The two orange bars are the same wallet "
            f"selling and buying back the same size — a round-trip."
        ),
        "sandwich": (
            f"Block {esc(ex.get('h'))}: {len(rows)} prints of {sym}. The two orange bars are one wallet's legs "
            f"around a victim's print in red — a sandwich."
        ),
        "organic": (
            f"Block {esc(ex.get('h'))}: consecutive organic prints of {sym}; the bps between them is the "
            f"quote-to-fill."
        ),
    }[kind]
    parts = [
        f'<svg class="block" viewBox="0 0 1200 {height}" role="img" aria-label="{label}" '
        f'xmlns="http://www.w3.org/2000/svg">',
        f"<title>{label}</title>",
        f'<line class="rail" x1="40" y1="{top}" x2="40" y2="{height - top}"/>',
    ]
    ys = {}
    for i, (row, a0) in enumerate(zip(rows, a0s, strict=True)):
        y = top + i * rowh
        w = max(28.0, a0 / mx * barmax)
        lg = row.get("lgid")
        cls = "print"
        if lg in legs:
            cls = f"leg l{legs.index(lg) + 1}"
        elif lg in victims:
            cls = "victim"
        elif kind == "organic" and lg in (ex.get("highlight") or []):
            cls = "fill"
        ys[lg] = (y, w)
        parts.append(
            f'<g class="row {cls}"><line class="tick" x1="34" y1="{y + 22}" x2="46" y2="{y + 22}"/>'
            f'<rect x="{x0}" y="{y + 9}" width="{w:.0f}" height="26" rx="5"/></g>'
        )
    if len(legs) == 2 and all(lg in ys for lg in legs):
        (y1, w1), (y2, w2) = ys[legs[0]], ys[legs[1]]
        xe1, xe2 = x0 + w1, x0 + w2
        xr = min(1180, max(xe1, xe2) + 34)
        r_ = abs(y2 - y1) / 2
        parts.append(
            f'<path class="hairpin" d="M{xe1:.0f} {y1 + 22} H{xr - r_:.0f} A{r_:.0f} {r_:.0f} 0 0 1 {xr - r_:.0f} {y2 + 22} '
            f'H{xe2 + 12:.0f} m10 -8 l-10 8 l10 8"/>'
        )
    parts.append("</svg>")
    if kind in ("round-trip", "sandwich") and len(leg_rows) == 2:
        a, b = leg_rows
        d = abs(float(b["a0"]) - float(a["a0"])) / float(a["a0"])
        key = (
            f"<span><i></i><span>a print in block {esc(ex.get('h'))} — bar length is its {sym} amount; "
            f"{len(rows)} of the block's prints are drawn</span></span>"
            f'<span><i class="leg"></i><span><b class="orange">lgid {esc(a["lgid"])} {esc(a["tp"])} '
            f'{float(a["a0"]):,.2f}</b> → <b class="orange">lgid {esc(b["lgid"])} {esc(b["tp"])} '
            f"{float(b['a0']):,.2f}</b> {sym}: the same wallet <b>{esc(short(a['ma'], 8))}</b>, "
            f"{'same transaction' if ex.get('same_tx') or a.get('tx') == b.get('tx') else 'same block'}, "
            f"sizes {d * 100:.1f} % apart"
            + (
                f' · <b class="red">{len(victims)} victim print{"s" if len(victims) != 1 else ""}</b> between the legs'
                if kind == "sandwich"
                else ""
            )
            + "</span></span>"
        )
    else:
        key = (
            f"<span><i></i><span>a print in block {esc(ex.get('h'))} — bar length is its {sym} amount</span></span>"
            f"<span><i></i><span>two consecutive organic prints — the bps between them is what a fill paid, computed in the rows below</span></span>"
        )
    return "\n".join(parts), key


def context_line(r, census):
    rule = census["hero"]["rule"] or enrich.HERO_RULE
    return (
        f"<b>{esc(r['symbol'])}</b> · {esc(r['platform'].title())} · last {r['window']['prints']} prints · "
        f"{r['window']['span_hours']} h · blocks {esc(r['window']['first_block'])}–{esc(r['window']['last_block'])} · "
        f"captured {utc_short(r['captured_utc'])} · keyless · "
        f'<span title="{esc(rule)}">chosen by rule: {esc(rule)}</span>'
    )


def table_rows(r):
    routed = r["decision"]["pool"]
    shown = hero_pool(r)["key"]
    out = []
    for i, p in enumerate(r["pools"]):
        rt, sw = p["round_trips"], p["sandwiches"]
        classes = []
        if p["key"] == routed:
            classes.append("routed")
        if rt["pairs"] or sw["count"]:
            classes.append("middle")
        name = f"{esc(p['venue'])} / {esc(p['quote'])}"
        if p.get("pools_merged") and p["pools_merged"] > 1:
            name += f"<small>×{p['pools_merged']}</small>"
        if p["key"] == routed:
            name += '<small class="mark">◀ route</small>'
        rt_txt = (
            f"{rt['pairs']} · {len(rt['wallets'])} wallet{'s' if len(rt['wallets']) != 1 else ''} · "
            f"{rt['share_volume'] * 100:.1f}%"
            if rt["pairs"]
            else "—"
        )
        tax = (
            f"{p['buy_tax']:.0f} / {p['sell_tax']:.0f}"
            if p.get("buy_tax") is not None and p.get("sell_tax") is not None
            else "—"
        )
        out.append(
            f'<tr class="{" ".join(classes)}" data-i="{i}" tabindex="0" aria-selected="{"true" if p["key"] == shown else "false"}">'
            f'<td class="pool">{name}</td>'
            f'<td class="mono">{p["n"]}</td>'
            f'<td class="mono">{p["n_organic"]}</td>'
            f'<td class="mono rt{" none" if not rt["pairs"] else ""}">{rt_txt}</td>'
            f'<td class="mono sw{" none" if not sw["count"] else ""}">{sw["count"]}</td>'
            f'<td class="mono q2f">{bps(p["q2f"]["p50_bps"])} / {bps(p["q2f"]["p90_bps"])} bps</td>'
            f'<td class="mono">{tax}</td>'
            f'<td class="mono">{usd(p.get("liq_usd"))}</td>'
            "</tr>"
        )
    return "\n".join(out)


def route_ctx(r):
    d = r["decision"]
    if not d["pool"]:
        return {"line": f"no route — {esc(d['why'])}", "rule": esc(recommend.RULE)}
    return {
        "line": (
            f"▶ route via {esc(d['venue'])} / {esc(d['quote'])} · cap slippage at {d['cap_pct']:.2f} %"
        ),
        "rule": (
            f"rule: {esc(recommend.RULE)} · organic p90 here {bps(d['p90_bps'])} bps · "
            f"{d['candidates']} candidate pool{'s' if d['candidates'] != 1 else ''}"
        ),
    }


def hero_pool(r):
    """The pool the headline is about: the widest round-trip share, else the most sandwiches,
    else the routed pool — the same order the headline itself falls through."""
    with_rt = [p for p in r["pools"] if p["round_trips"]["pairs"]]
    if with_rt:
        return max(with_rt, key=lambda p: p["round_trips"]["share_volume"])
    with_sw = [p for p in r["pools"] if p["sandwiches"]["count"]]
    if with_sw:
        return max(with_sw, key=lambda p: p["sandwiches"]["count"])
    return next((p for p in r["pools"] if p["key"] == r["decision"]["pool"]), r["pools"][0])


def example_ctx(r, platforms, pool=None):
    """The raw-rows panel for one pool (the headline's pool by default)."""
    pool = pool or hero_pool(r)
    ex = pool.get("example")
    txuf = (platforms.get(r["platform"]) or {}).get("txuf")
    if not ex:
        return {
            "title": f"{esc(pool['venue'])} / {esc(pool['quote'])} — raw rows",
            "cap": "this pool has a single print in the window; nothing to compare",
            "table": "",
            "arith": "",
            "json": "[]",
        }
    legs, victims = set(ex["highlight"]), set(ex.get("victims") or [])
    kind = ex["kind"]
    rows_html = [
        "<table><thead><tr><th>lgid</th><th>maker</th><th>side</th><th>a0 (base)</th><th>a1 (quote)</th>"
        "<th>a1 / a0</th><th>tx</th></tr></thead><tbody>"
    ]
    for row in ex["rows"][:14]:
        lg = row.get("lgid")
        cls = (
            "leg"
            if lg in legs
            else ("victim" if lg in victims else ("fill" if kind == "organic" else ""))
        )
        q = price(row)
        tx = row.get("tx") or ""
        link = (
            f'<a href="{esc(txuf.replace("%s", tx))}" target="_blank" rel="noopener noreferrer" class="mono">{esc(short(tx, 8))}{EXT}</a>'
            if txuf and tx
            else f'<span class="mono">{esc(short(tx, 8))}</span>'
        )
        rows_html.append(
            f'<tr class="{cls}"><td class="mono">{esc(lg)}</td><td class="mono" title="{esc(row.get("ma"))}">{esc(short(row.get("ma"), 10))}</td>'
            f'<td>{esc(row.get("tp"))}</td><td class="mono">{float(row.get("a0") or 0):,.4f}</td>'
            f'<td class="mono">{float(row.get("a1") or 0):,.6f}</td><td class="mono">{q:.4e}</td><td>{link}</td></tr>'
            if q is not None
            else f'<tr class="{cls}"><td class="mono">{esc(lg)}</td><td class="mono">{esc(short(row.get("ma"), 10))}</td><td>{esc(row.get("tp"))}</td><td colspan="4">unpriceable row</td></tr>'
        )
    rows_html.append("</tbody></table>")
    what = {
        "round-trip": "the block that holds the first round-trip — both legs in orange",
        "sandwich": "the block that holds the first sandwich — the legs in orange, the victim in red",
        "organic": "two consecutive organic prints in one block — the bps between them, computed inline",
    }[kind]
    cap = (
        f'block {esc(ex["h"])} · {what} · endpoint <span class="mono">/public-api/v1/dex/tokens/transactions</span> · '
        f'<a href="{REPO}/blob/main/{esc(r.get("tape", "data/"))}" target="_blank" rel="noopener noreferrer">the whole tape{EXT}</a>'
    )
    return {
        "title": f"{esc(pool['venue'])} / {esc(pool['quote'])} — raw rows ({kind})",
        "cap": cap,
        "table": "\n".join(rows_html),
        "arith": "".join(f"<li>{esc(line)}</li>" for line in ex["arithmetic"]),
        "json": esc(json.dumps(ex["rows"][:14], indent=1, sort_keys=True)),
    }


def census_ctx(census, receipts):
    """The census as the page shows it: the token switcher, the stat band and the spread line."""
    w = census.get("widest_spread") or {}
    others = [h for h in census.get("heroes") or [] if h and h["platform"] != "ethereum"]
    others_txt = (
        "Also measured by the same rule: "
        + ", ".join(
            f"{esc(h['pair'])} on {esc(h['platform'].upper() if h['platform'] == 'bsc' else h['platform'].title())}"
            for h in others
        )
        + "."
        if others
        else ""
    )
    buttons = []
    # indexes into the embedded list, which holds the Ethereum receipts only (see slim())
    for i, r in enumerate([x for x in receipts if x["platform"] == "ethereum"]):
        rt = sum(p["round_trips"]["pairs"] for p in r["pools"])
        sw = sum(p["sandwiches"]["count"] for p in r["pools"])
        note = f"{rt} rt" if rt else (f"{sw} sw" if sw else "quiet")
        pressed = "true" if r["symbol"] == census["hero"]["symbol"] else "false"
        buttons.append(
            f'<button type="button" data-i="{i}" aria-pressed="{pressed}">{esc(r["symbol"])}<small>{note}</small></button>'
        )
    rows = census["rows"]
    longest = max(rows, key=lambda x: x["span_hours"])
    return {
        "tokens": "\n".join(buttons),
        "tokens_n": census["tokens"],
        "chains": len({x["platform"] for x in rows}),
        "pinned": len([x for x in rows if x["platform"] == "ethereum"]) - 1,
        "prints": f"{census['prints']:,}",
        "pools": f"{census['pools']:,}",
        "sandwiches": census["sandwiches"],
        "sandwich_rate": f"{census['sandwiches'] / census['prints'] * 100:.3f} %",
        "round_trips": census["round_trip_pairs"],
        "rt_wallets": len(census["round_trip_wallets"]),
        "others": others_txt,
        "longest_symbol": esc(longest["symbol"]),
        "longest_span": f"{longest['span_hours']:.0f}",
        "spread.symbol": esc(w.get("symbol", "—")),
        "spread.ratio": f"{w.get('ratio', 0):.1f}",
        "spread.low": bps((w.get("low") or {}).get("p50_bps")),
        "spread.high": bps((w.get("high") or {}).get("p50_bps")),
        "spread.low_pool": esc((w.get("low") or {}).get("pool", "—")),
        "spread.high_pool": esc((w.get("high") or {}).get("pool", "—")),
    }


def receipt_ctx(r):
    calls = [c for c in r["calls"] if c.get("ok")]
    tx_calls = [c for c in calls if "tokens/transactions" in str(c.get("url", ""))]
    first = tx_calls[0] if tx_calls else (calls[0] if calls else {})
    statuses = sorted({str(c.get("status")) for c in r["calls"]})
    items = [
        ("endpoint", '<span class="mono">/public-api/v1/dex/tokens/transactions</span>'),
        ("calls", f"{len(r['calls'])} · {len(tx_calls)} pages of 100 · HTTP {', '.join(statuses)}"),
        ("credits used", f'<span class="mono">{r["credits_used"]}</span> — {esc(r["auth"])}'),
        (
            "captured",
            f'<span class="mono">{esc(r["captured_utc"])}</span> · {r["wall_s"]} s wall clock',
        ),
        ("first page sha256", f'<span class="mono">{esc(first.get("sha256", "—"))}</span>'),
        (
            "first request",
            f'<a class="mono" href="{esc(first.get("url", "#"))}" target="_blank" rel="noopener noreferrer">{esc(first.get("url", "—"))}{EXT}</a>',
        ),
        (
            "re-derive",
            f'<span class="mono">python3 scripts/verify_tape.py</span> · <a href="{REPO}/blob/main/docs/proof/" target="_blank" rel="noopener noreferrer">docs/proof/{EXT}</a> · <a href="evidence.html">every call →</a>',
        ),
    ]
    return "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in items)


def proof_links(census, r):
    """Four receipt files a judge opens first, in the family's proof-grid shape."""
    hp = census["hero"]["pool"]
    pool = next(p for p in r["pools"] if p["venue"] == hp["venue"] and p["quote"] == hp["quote"])
    run2 = _run_ctx("live_run")
    run3 = _run_ctx("live_run_quiet")
    items = [
        (
            Path(r.get("tape", "tape_x.json")).stem.replace("tape_", "") + ".json",
            f"{r['symbol']} · {r['window']['prints']} prints · {pool['round_trips']['share_volume'] * 100:.1f} % round-tripped · {utc_short(r['captured_utc'])}",
        ),
        (
            "census.json",
            f"{census['tokens']} tokens · {census['prints']:,} prints · {census['sandwiches']} sandwiches · {census['round_trip_pairs']} round-trips",
        ),
        ("live_run.json", f"the bare command · {run2['share']} · {run2['captured']}"),
        ("live_run_quiet.json", f"the bare command · {run3['share']} · {run3['captured']}"),
    ]
    return "".join(
        f'<a href="{REPO}/blob/main/docs/proof/{esc(f)}" target="_blank" rel="noopener noreferrer">'
        f'<div class="f">docs/proof/{esc(f)}{EXT}</div>'
        f'<div class="m">{esc(m)}</div></a>'
        for f, m in items
    )


def endpoint_counts(receipts):
    counts = dict.fromkeys((e for e, _ in ENDPOINTS), 0)
    for r in receipts:
        for c in r["calls"]:
            url = str(c.get("url", ""))
            for e in counts:
                if e in url:
                    counts[e] += 1
    return counts


def api_ctx(receipts):
    counts = endpoint_counts(receipts)
    rows = []
    for i, (e, role) in enumerate(ENDPOINTS):
        cls = ' class="engine"' if i == 0 else ""
        rows.append(
            f"<tr{cls}><td><code>/public-api{esc(e)}</code></td><td>{esc(role)}</td>"
            f'<td>none</td><td class="n">{counts[e]}</td></tr>'
        )
    return {"rows": "".join(rows), "count": len(ENDPOINTS)}


def findings_ctx():
    """The three API findings the page shows, each with its number from the spike receipt."""
    spike = json.loads((PROOF / "spike.json").read_text())
    cors = spike.get("cors") or {}
    tapes = spike.get("tapes") or {}
    sym, fields = max(
        ((s, t.get("fields") or {}) for s, t in tapes.items()),
        key=lambda st: sum((st[1].get("q_mismatch_by_venue") or {}).values()),
    )
    mism = fields.get("q_mismatch_by_venue") or {}
    return {
        "cors_sent": len(cors.get("headers_sent") or {}),
        "cors_allow_origin": "sent" if cors.get("allow_origin_present") else "not sent",
        "q_symbol": esc(sym),
        "q_rows": fields.get("rows", 0),
        "q_ok": fields.get("q_equals_a1_over_a0_within_1e-6", 0),
        "q_bad": sum(mism.values()),
        "q_v4": sum(v for k, v in mism.items() if "v4" in k),
        "q_v3": sum(v for k, v in mism.items() if "v3" in k),
    }


def feedback_n():
    """How many numbered findings FEEDBACK.md carries — counted, not typed."""
    text = (BUILD / "FEEDBACK.md").read_text()
    return len(re.findall(r"^## \d+\. ", text, re.M))


def runs_ctx(census, receipts):
    """The same pair, one night: the spike, the capture behind the page, and the two bare
    runs — the round-trip share of the hero pool in each, from its own receipt."""
    r = hero_receipt(census, receipts)
    hp = census["hero"]["pool"]
    pool = next(p for p in r["pools"] if p["venue"] == hp["venue"] and p["quote"] == hp["quote"])
    spike = json.loads((PROOF / "spike.json").read_text())
    sp = spike["answer"]["hero_pool"]
    run2, run3 = _run_ctx("live_run"), _run_ctx("live_run_quiet")
    windows = [
        {
            "t": utc_hhmm(spike["captured_utc"]),
            "share": sp["round_trip_share_of_volume"],
            "m": f"{sp['round_trips_A_A']} round-trips · {len(sp['round_trip_wallets'])} wallets · the day-1 spike",
            "f": "spike.json",
        },
        {
            "t": utc_hhmm(r["captured_utc"]),
            "share": pool["round_trips"]["share_volume"],
            "m": f"{pool['round_trips']['pairs']} round-trips · {len(pool['round_trips']['wallets'])} wallets · the capture behind this page",
            "f": Path(r.get("tape", "tape_x.json")).stem.replace("tape_", "") + ".json",
        },
        {
            "t": utc_hhmm(run2["captured_utc"]),
            "share": run2["share_num"],
            "m": f"{run2['pairs']} round-trips · {run2['wallets']} wallet{'s' if run2['wallets'] != 1 else ''} · the bare command, {run2['wall_s']} s",
            "f": "live_run.json",
        },
        {
            "t": utc_hhmm(run3["captured_utc"]),
            "share": run3["share_num"],
            "m": f"{run3['pairs']} round-trips · every print organic · the bare command, {run3['wall_s']} s",
            "f": "live_run_quiet.json",
        },
    ]
    cards = []
    for w in windows:
        quiet = " quiet" if not w["share"] else ""
        cards.append(
            f'<div class="run"><div class="t">{esc(w["t"])} UTC</div>'
            f'<div class="v{quiet}">{w["share"] * 100:.1f}%</div>'
            f'<div class="m">{esc(w["m"])} · <a href="{REPO}/blob/main/docs/proof/{esc(w["f"])}" target="_blank" rel="noopener noreferrer">{esc(w["f"])}{EXT}</a></div></div>'
        )
    return {"cards": "".join(cards), "n": len(windows)}


def term_ctx():
    """The terminal: the bare command and the lines it printed, from the receipt it kept."""
    m = json.loads((PROOF / "live_run.json").read_text())
    res = m["results"][0]
    hr = m["hero_rule"]
    d = res["decision"]
    hero = next((p for p in res["pools"] if p["round_trips"]["pairs"]), res["pools"][0])
    rt = hero["round_trips"]
    lines = [
        '<span class="p">$</span> <span class="cmd">git clone https://github.com/edycutjong/middleman.git &amp;&amp; cd middleman</span>',
        '<span class="p">$</span> <span class="cmd">python3 scripts/middleman.py</span>',
        "",
        f'<span class="dim">{esc(res["engine"])} — keyless, live</span>',
        "",
        f'<span class="dim">hero rule: {esc(hr["rule"])}</span>',
        f'<span class="dim">  → {esc(hr["name"])}  {esc(hr["address"])}</span>',
        "",
        f'<span class="cmd">{esc(res["symbol"])} · {esc(res["platform"])} · {res["window"]["prints"]} prints · {res["window"]["span_hours"]} h · blocks {esc(res["window"]["first_block"])}–{esc(res["window"]["last_block"])} · captured {esc(res["captured_utc"])} · keyless</span>',
        "",
    ]
    if rt["pairs"]:
        lines.append(
            f'  <span class="hi">{rt["share_volume"] * 100:.1f}% of {esc(hero["venue"])} / {esc(hero["quote"])} volume is '
            f'{len(rt["wallets"])} wallet(s) buying back what they just sold</span> <span class="dim">({rt["pairs"]} round-trips'
            f"{', same transaction' if (rt.get('same_tx_share') or 0) >= 0.5 else ''})</span>"
        )
    else:
        lines.append(
            '  <span class="ok">no middleman found in this window — every print organic</span>'
        )
    lines.append("")
    for p in res["pools"]:
        prt = p["round_trips"]
        rt_txt = (
            f'<span class="hi">{prt["pairs"]} · {len(prt["wallets"])} wallet(s) · {prt["share_volume"] * 100:.1f}%</span>'
            if prt["pairs"]
            else '<span class="dim">—</span>'
        )
        mark = '  <span class="ok">◀ route</span>' if p["key"] == d["pool"] else ""
        lines.append(
            f'  {esc(p["venue"])} / {esc(p["quote"])}  <span class="dim">{p["n"]} prints · {p["n_organic"]} organic ·</span> '
            f'{rt_txt} <span class="dim">·</span> <span class="bl">{bps(p["q2f"]["p50_bps"])} / {bps(p["q2f"]["p90_bps"])} bps</span>{mark}'
        )
    lines.append("")
    if d["pool"]:
        lines.append(
            f'  <span class="ok">▶ route via {esc(d["venue"])} / {esc(d["quote"])} · cap slippage at {d["cap_pct"]:.2f} %</span>   '
            f'<span class="dim">(organic p90 {bps(d["p90_bps"])} bps)</span>'
        )
    lines.append(
        f'<span class="dim">wrote docs/proof/live_run.json  ({m["wall_clock_s"]:.1f}s wall clock, {m["credits_used"]} credits — keyless)</span>'
    )
    return {
        "term": "\n".join(lines),
        "cmd": "git clone https://github.com/edycutjong/middleman.git && cd middleman && python3 scripts/middleman.py",
    }


def slim(r):
    """The receipt as the page embeds it: everything the table and the drawer need, no call list."""
    return {
        "symbol": r["symbol"],
        "platform": r["platform"],
        "address": r["address"],
        "captured_utc": r["captured_utc"],
        "window": r["window"],
        "decision": r["decision"],
        "coverage": r.get("coverage"),
        "tape": r.get("tape"),
        "calls_n": len(r["calls"]),
        "first_url": next((c.get("url") for c in r["calls"] if c.get("ok")), None),
        "first_sha256": next((c.get("sha256") for c in r["calls"] if c.get("ok")), None),
        "wall_s": r["wall_s"],
        "pools": [
            {
                **{k: v for k, v in p.items() if k != "example"},
                "example": p["example"] and {**p["example"], "rows": p["example"]["rows"][:14]},
            }
            for p in r["pools"]
        ],
    }


def og_version():
    if not OG_IMAGE.exists():
        return "none"
    return hashlib.sha1(OG_IMAGE.read_bytes()).hexdigest()[:8]


def render(template, ctx):
    out = template
    for k, v in ctx.items():
        out = out.replace("{{" + k + "}}", str(v))
    left = sorted(set(re.findall(r"\{\{([a-zA-Z0-9_.]+)\}\}", out)))
    if left:
        sys.exit(f"unfilled slots: {left}")
    return out


def front_page(census, platforms, receipts):
    r = hero_receipt(census, receipts)
    hero = hero_ctx(r, census)
    pool = hero_pool(r)
    judge = judge_ctx(census, platforms, receipts)
    ctx = {f"hero.{k}": v for k, v in hero.items()}
    ctx.update({f"hero.{k}": v for k, v in lead_ctx(r, census, hero, pool).items()})
    ctx.update({f"route.{k}": v for k, v in route_ctx(r).items()})
    ctx.update({f"rows.{k}": v for k, v in example_ctx(r, platforms, pool).items()})
    cen = census_ctx(census, receipts)
    ctx.update({(k if k.startswith("spread.") else f"census.{k}"): v for k, v in cen.items()})
    api = api_ctx(receipts)
    ctx.update({f"api.{k}": v for k, v in api.items()})
    ctx.update({f"find.{k}": v for k, v in findings_ctx().items()})
    runs = runs_ctx(census, receipts)
    term = term_ctx()
    ctx.update(
        {
            "context": context_line(r, census),
            "table_rows": table_rows(r),
            "receipt": receipt_ctx(r),
            "proof_links": proof_links(census, r),
            "runs": runs["cards"],
            "runs.n": runs["n"],
            "term": term["term"],
            "cmd": esc(term["cmd"]),
            "feedback.n": feedback_n(),
            "version": DECK_VERSION,
            "receipts_json": json.dumps(
                {
                    "hero": census["hero"],
                    "platforms": platforms,
                    "rule": recommend.RULE,
                    "receipts": [slim(x) for x in receipts if x["platform"] == "ethereum"],
                },
                separators=(",", ":"),
            ).replace("</", "<\\/"),
            "repo": REPO,
            "repo_short": REPO_SHORT,
            "site": SITE_URL,
            "event": EVENT,
            "author": AUTHOR,
            "x_handle": X_HANDLE,
            "og.v": og_version(),
        }
    )
    # the published counts and the benchmarks, the same slots /judge and the deck fill
    for k in (
        "tests_total",
        "tests_offline",
        "tests_live",
        "property_cases",
        "bench.replay_p50",
        "bench.replay_p95",
        "bench.replay_n",
        "bench.replay_prints",
        "bench.live_p50",
        "bench.live_p95",
        "bench.live_n",
    ):
        ctx[k] = judge[k]
    return render((TEMPLATES / "index.html").read_text(), ctx)


# ── the evidence page ────────────────────────────────────────────────────────


def evidence_page(census, platforms, receipts):
    hero = hero_receipt(census, receipts)
    sections, total = [], 0
    counts = endpoint_counts(receipts)
    for r in receipts:
        rows = []
        for c in r["calls"]:
            total += 1
            url = str(c.get("url", ""))
            ok = c.get("ok")
            rows.append(
                f'<tr><td class="{"ok" if ok else "err"} mono">{esc(c.get("status") or "—")}</td>'
                f'<td class="mono">{esc(c.get("utc", ""))}</td>'
                f'<td class="mono">{esc(c.get("elapsed_ms", ""))}</td>'
                f'<td class="mono">{esc(c.get("sha256", "") or c.get("error", ""))}</td>'
                f'<td class="mono">{esc(c.get("credit_count", 0) if ok else "")}</td>'
                f'<td class="url mono"><a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(url.replace("https://pro-api.coinmarketcap.com", ""))}</a></td></tr>'
            )
        sections.append(
            f"<h2>{esc(r['symbol'])} · {esc(r['platform'])} · {r['window']['prints']} prints · "
            f'{len(r["calls"])} calls · <a href="{REPO}/blob/main/docs/proof/{esc(Path(r.get("tape", "x")).stem.replace("tape_", ""))}.json" target="_blank" rel="noopener noreferrer">receipt ↗</a></h2>'
            '<div class="tw"><table><thead><tr><th>HTTP</th><th>UTC</th><th>ms</th><th>sha256 of body</th><th>credits</th><th>request</th></tr></thead>'
            f"<tbody>{''.join(rows)}</tbody></table></div>"
        )
    rules = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in hero["rules"].items())
    endpoints = "".join(
        f'<tr><td class="mono">{i}</td><td class="mono">/public-api{esc(e)}</td><td>{esc(role)}</td><td class="mono">{counts[e]}</td></tr>'
        for i, (e, role) in enumerate(ENDPOINTS, 1)
    )
    ctx = {
        "calls_n": total,
        "tokens_n": len(receipts),
        "captured": utc_short(census["captured_utc"]),
        "rules": rules,
        "sections": "\n".join(sections),
        "endpoints": endpoints,
        "hero.address": hero["address"],
        "hero.symbol": hero["symbol"],
        "repo": REPO,
        "repo_short": REPO_SHORT,
        "site": SITE_URL,
        "author": AUTHOR,
        "x_handle": X_HANDLE,
        "og.v": og_version(),
    }
    return render((TEMPLATES / "evidence.html").read_text(), ctx)


# ── the judge page ───────────────────────────────────────────────────────────


def judge_ctx(census, platforms, receipts):
    """The receipt-derived slots /judge and the deck share: the hero pool's numbers, the
    route, the census totals, the published counts and the benchmarks."""
    r = hero_receipt(census, receipts)
    hp = census["hero"]["pool"]
    pool = next(p for p in r["pools"] if p["venue"] == hp["venue"] and p["quote"] == hp["quote"])
    rt = pool["round_trips"]
    d = r["decision"]
    cov = r.get("coverage") or {}
    replay = json.loads((PROOF / "bench_replay.json").read_text())
    live = json.loads((PROOF / "bench_live.json").read_text())
    tx_calls = [c for c in r["calls"] if "tokens/transactions" in str(c.get("url", ""))]
    ctx = {
        "hero.symbol": esc(r["symbol"]),
        "hero.address": esc(r["address"]),
        "hero.venue": esc(pool["venue"]),
        "hero.quote": esc(pool["quote"]),
        "hero.share": f"{rt['share_volume'] * 100:.1f} %",
        "hero.wallets_n": len(rt["wallets"]),
        "hero.pairs": rt["pairs"],
        "hero.rt_usd": f"${rt['volume_usd']:,.0f}",
        "hero.pool_usd": f"${pool['volume_usd']:,.0f}",
        "hero.sandwiches": pool["sandwiches"]["count"],
        "hero.organic_p50": bps(pool["q2f"]["p50_bps"]),
        "hero.organic_p90": bps(pool["q2f"]["p90_bps"]),
        "hero.naive_p50": bps(pool["naive"]["p50_bps"]),
        "hero.span": r["window"]["span_hours"],
        "hero.coverage": (
            f"{cov['window_share_of_24h']:.0%}" if cov.get("window_share_of_24h") else "unknown"
        ),
        "hero.file": esc(Path(r.get("tape", "tape_x.json")).stem.replace("tape_", "") + ".json"),
        "hero_calls": len(r["calls"]),
        "captured": utc_short(r["captured_utc"]),
        "wall_s": r["wall_s"],
        "pages": len(tx_calls),
        "prints": r["window"]["prints"],
        "platform": esc(r["platform"].title()),
        "rule": esc(census["hero"]["rule"] or enrich.HERO_RULE),
        "auth": esc(r["auth"]),
        "route": (
            f"{esc(d['venue'])} / {esc(d['quote'])} · cap slippage at {d['cap_pct']:.2f} % "
            f"(organic p90 {bps(d['p90_bps'])} bps)"
            if d["pool"]
            else f"no route — {esc(d['why'])}"
        ),
        "census.sandwiches": census["sandwiches"],
        "census.prints": f"{census['prints']:,}",
        "census.tokens": census["tokens"],
        "calls_n": sum(len(x["calls"]) for x in receipts),
        "tokens_n": len(receipts),
        "tests_total": TESTS_TOTAL,
        "tests_offline": TESTS_OFFLINE,
        "tests_live": TESTS_LIVE,
        "property_cases": f"{PROPERTY_CASES:,}",
        "bench.replay_p50": f"{replay['detect']['p50']:.1f}",
        "bench.replay_p95": f"{replay['detect']['p95']:.1f}",
        "bench.replay_n": replay["detect"]["n"],
        "bench.replay_prints": replay["prints"],
        "bench.live_p50": f"{live['fetch']['p50'] / 1000:.1f}",
        "bench.live_p95": f"{live['fetch']['p95'] / 1000:.1f}",
        "bench.live_n": live["fetch"]["n"],
        "repo": REPO,
        "repo_short": REPO_SHORT,
        "site": SITE_URL,
        "site_short": SITE_SHORT,
        "event": EVENT,
        "author": AUTHOR,
        "x_handle": X_HANDLE,
        "og.v": og_version(),
    }
    return ctx


def judge_page(census, platforms, receipts):
    """One page for one reader: the claim, the 30-second path, the receipt, the real
    reproduce command, the limitations. Every number from the receipts, like the other two."""
    return render((TEMPLATES / "judge.html").read_text(), judge_ctx(census, platforms, receipts))


# ── the deck ─────────────────────────────────────────────────────────────────


def _run_ctx(name):
    """The zero-flag receipts DEMO.md transcribes (scripts/middleman.py --json): the routed
    pool's round-trip share, wall clock and capture time — the "number moves" timeline."""
    m = json.loads((PROOF / f"{name}.json").read_text())
    res = m["results"][0]
    pool = next(
        (p for p in res["pools"] if p["key"] == res["decision"]["pool"]),
        res["pools"][0],
    )
    rt = pool["round_trips"]
    return {
        "captured": utc_short(m["captured_utc"]),
        "captured_utc": m["captured_utc"],
        "share": f"{rt['share_volume'] * 100:.1f} %",
        "share_num": rt["share_volume"],
        "pairs": rt["pairs"],
        "wallets": len(rt["wallets"]),
        "wall_s": f"{m['wall_clock_s']:.1f}",
    }


def deck_page(census, platforms, receipts):
    """The pitch deck at /pitch — twelve slides, every number a slot from the same receipts
    as /judge, formatted the way DEMO.md prints them (one decimal on the wall clock)."""
    ctx = judge_ctx(census, platforms, receipts)
    r = hero_receipt(census, receipts)
    cov = r.get("coverage") or {}
    spread = census.get("widest_spread") or {}
    replay = json.loads((PROOF / "bench_replay.json").read_text())
    ctx.update(
        {
            "version": DECK_VERSION,
            "wall_s": f"{r['wall_s']:.1f}",
            "hero.share_tight": ctx["hero.share"].replace(" %", "%"),
            "hero.coverage_1": (
                f"{cov['window_share_of_24h'] * 100:.1f} %"
                if cov.get("window_share_of_24h")
                else "an unknown share"
            ),
            "hero.txs_24h": f"{cov.get('num_transactions_24h') or 0:,}",
            "cap_pct": f"{r['decision']['cap_pct']:.2f}",
            "census.pools": census["pools"],
            "census.round_trips": census["round_trip_pairs"],
            "census.rt_wallets": len(census["round_trip_wallets"]),
            "census.sandwich_rate": f"{census['sandwiches'] / census['prints'] * 100:.3f} %",
            "spread.symbol": esc(spread.get("symbol", "—")),
            "spread.ratio": f"{spread.get('ratio', 0):.1f}",
            "spread.low": bps((spread.get("low") or {}).get("p50_bps")),
            "spread.high": bps((spread.get("high") or {}).get("p50_bps")),
            "spread.low_pool": esc((spread.get("low") or {}).get("pool", "—")),
            "spread.high_pool": esc((spread.get("high") or {}).get("pool", "—")),
            "bench.replay_prints": replay["prints"],
        }
    )
    ctx.update({f"run2.{k}": v for k, v in _run_ctx("live_run").items()})
    ctx.update({f"run3.{k}": v for k, v in _run_ctx("live_run_quiet").items()})
    return render((TEMPLATES / "deck.html").read_text(), ctx)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    census, platforms, receipts = load_all()
    pages = {
        SITE / "index.html": front_page(census, platforms, receipts),
        SITE / "evidence.html": evidence_page(census, platforms, receipts),
        SITE / "judge.html": judge_page(census, platforms, receipts),
        SITE / "pitch" / "index.html": deck_page(census, platforms, receipts),
    }
    drift = []
    for path, content in pages.items():
        if check:
            if not path.exists() or path.read_text() != content:
                drift.append(str(path.relative_to(BUILD)))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
            print(f"wrote {path.relative_to(BUILD)} ({len(content.encode()) / 1024:.0f} KiB)")
    if check:
        if drift:
            print(
                f"drift: {', '.join(drift)} — the page is not what its receipts render; run make site"
            )
            return 1
        print("site/ is what docs/proof/*.json renders")
    return 0


if __name__ == "__main__":
    sys.exit(main())
