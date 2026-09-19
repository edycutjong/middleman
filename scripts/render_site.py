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

from middleman import enrich, recommend  # noqa: E402

TEMPLATES = BUILD / "scripts" / "site_templates"
PROOF = BUILD / "docs" / "proof"
SITE = BUILD / "site"

REPO = "https://github.com/edycutjong/middleman"
REPO_SHORT = "github.com/edycutjong/middleman"
SITE_URL = "https://middleman-cmc.vercel.app"
SITE_SHORT = "middleman-cmc.vercel.app"
# The deck's version stamp. The committed HTML carries the honest fallback — no release exists
# until release.yml tags one — and .github/workflows/pages.yml substitutes the repository's
# latest tag over it at deploy, so the deck, the README badge and the live app agree. It is
# not read from `git describe` here because the CI job that gates site/ against its templates
# clones shallow with no tags, and a render that depended on tags would drift there.
DECK_VERSION = "v0.0.0-dev"
# The counts /judge publishes. tests/test_published_counts.py fails if they drift from the suite.
TESTS_TOTAL, TESTS_OFFLINE, TESTS_LIVE = 145, 139, 6
PROPERTY_CASES = 1000
EVENT = "https://dorahacks.io/hackathon/coinmarketcap-api-202609/detail"
AUTHOR = "Edy Cu"
X_HANDLE = "@edycutjong"
OG_IMAGE = SITE / "assets" / "og-image.png"

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
            f'<a href="{esc(txuf.replace("%s", tx))}" target="_blank" rel="noopener noreferrer" class="mono">{esc(short(tx, 8))} ↗</a>'
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
        f'<a href="{REPO}/blob/main/{esc(r.get("tape", "data/"))}" target="_blank" rel="noopener noreferrer">the whole tape ↗</a>'
    )
    return {
        "title": f"{esc(pool['venue'])} / {esc(pool['quote'])} — raw rows ({kind})",
        "cap": cap,
        "table": "\n".join(rows_html),
        "arith": "".join(f"<li>{esc(line)}</li>" for line in ex["arithmetic"]),
        "json": esc(json.dumps(ex["rows"][:14], indent=1, sort_keys=True)),
    }


def census_ctx(census, receipts):
    w = census.get("widest_spread")
    strip = (
        f"<span><b>{census['tokens']}</b> tokens</span>"
        f"<span><b>{census['prints']:,}</b> prints</span>"
        f'<span><b class="d">{census["sandwiches"]}</b> sandwiches</span>'
        f'<span><b class="m">{census["round_trip_pairs"]}</b> round-trips by <b class="m">{len(census["round_trip_wallets"])}</b> wallets</span>'
    )
    if w:
        strip += (
            f'<span>widest sibling spread <b class="o">{esc(w["symbol"])} {w["ratio"]:.1f}×</b> '
            f"({esc(w['low']['pool'])} {bps(w['low']['p50_bps'])} vs {esc(w['high']['pool'])} {bps(w['high']['p50_bps'])} bps)</span>"
        )
    others = [h for h in census.get("heroes") or [] if h and h["platform"] != "ethereum"]
    if others:
        strip += (
            "<span>also measured by the same rule: "
            + ", ".join(
                f"{esc(h['pair'])} on {esc(h['platform'].upper() if h['platform'] == 'bsc' else h['platform'].title())}"
                for h in others
            )
            + "</span>"
        )
    buttons = []
    # indexes into the embedded list, which holds the Ethereum receipts only (see slim())
    for i, r in enumerate([x for x in receipts if x["platform"] == "ethereum"]):
        rt = sum(p["round_trips"]["pairs"] for p in r["pools"])
        sw = sum(p["sandwiches"]["count"] for p in r["pools"])
        note = f"{rt} rt" if rt else (f"{sw} sw" if sw else "clean")
        pressed = "true" if r["symbol"] == census["hero"]["symbol"] else "false"
        buttons.append(
            f'<button type="button" data-i="{i}" aria-pressed="{pressed}">{esc(r["symbol"])}<small>{note}</small></button>'
        )
    return {"strip": strip, "tokens": "\n".join(buttons)}


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
            f'<a class="mono" href="{esc(first.get("url", "#"))}" target="_blank" rel="noopener noreferrer">{esc(first.get("url", "—"))}</a>',
        ),
        (
            "re-derive",
            f'<span class="mono">python3 scripts/verify_tape.py</span> · <a href="{REPO}/blob/main/docs/proof/" target="_blank" rel="noopener noreferrer">docs/proof/ ↗</a> · <a href="evidence.html">every call →</a>',
        ),
    ]
    return "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in items)


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
    ctx = {f"hero.{k}": v for k, v in hero.items()}
    ctx.update({f"route.{k}": v for k, v in route_ctx(r).items()})
    ctx.update({f"rows.{k}": v for k, v in example_ctx(r, platforms).items()})
    ctx.update({f"census.{k}": v for k, v in census_ctx(census, receipts).items()})
    ctx.update(
        {
            "context": context_line(r, census),
            "table_rows": table_rows(r),
            "receipt": receipt_ctx(r),
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
    return render((TEMPLATES / "index.html").read_text(), ctx)


# ── the evidence page ────────────────────────────────────────────────────────


def evidence_page(census, platforms, receipts):
    hero = hero_receipt(census, receipts)
    sections, total = [], 0
    counts = dict.fromkeys((e for e, _ in ENDPOINTS), 0)
    for r in receipts:
        rows = []
        for c in r["calls"]:
            total += 1
            url = str(c.get("url", ""))
            for e in counts:
                if e in url:
                    counts[e] += 1
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
        "share": f"{rt['share_volume'] * 100:.1f} %",
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
            "census.sandwich_rate": f"{census['sandwiches'] / census['prints'] * 100:.3f}\u00a0%",
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
