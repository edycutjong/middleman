/* Middleman — the engine, ported to the browser, and the page's interactions.
 *
 * The detector below is a line-for-line port of middleman/detect.py, cost.py and recommend.py.
 * tests/test_js_parity.py runs it under node over the committed tape and diffs every pool
 * row against the Python engine, so the live paste box and the committed table are computed
 * identically. Nothing here holds a key; /api/swaps is a keyless passthrough.
 */
(function () {
  'use strict';
  const SIZE_TOL = 0.05, MAX_VICTIMS = 4, MIN_ORGANIC = 50, CAP_STEP_PCT = 0.05, BPS = 10000;
  const RULE = 'lowest organic p90 quote-to-fill among pools with ≥ 50 organic prints';
  const REPO = 'https://github.com/edycutjong/middleman';
  // The functions under api/ live on Vercel. On Vercel — and on scripts/serve.js, which routes
  // api/ the same way from a fresh clone — the proxy is same-origin. Anywhere else the static
  // page is hosted (GitHub Pages at middleman.edycu.dev, a file server) the fetch goes to the
  // Vercel deployment by absolute URL; api/swaps.js and api/health.js send
  // Access-Control-Allow-Origin: * and answer OPTIONS, and the request carries no custom
  // header, so it is a simple cross-origin GET with no preflight.
  const VERCEL = 'https://middleman-cmc.vercel.app';
  const host = (typeof location !== 'undefined' && location.hostname) || '';
  const API_BASE = (/\.vercel\.app$/.test(host) || host === 'localhost' || host === '127.0.0.1') ? '' : VERCEL;

  // ── detect ─────────────────────────────────────────────────────────────────
  const toInt = (v) => { const n = parseInt(String(v == null ? '' : v).trim(), 10); return Number.isFinite(n) ? n : null; };
  const toF = (v) => { const n = parseFloat(v); return Number.isFinite(n) ? n : null; };
  const side = (r) => String(r.tp == null ? '' : r.tp).toLowerCase();
  const sortKey = (r) => { const h = toInt(r.h), l = toInt(r.lgid); return h == null || l == null ? null : [h, l]; };
  function order(rows) {
    return rows.map((r) => [sortKey(r), r]).filter((kr) => kr[0] !== null)
      .sort((a, b) => a[0][0] - b[0][0] || a[0][1] - b[0][1]).map((kr) => kr[1]);
  }
  const unplaceable = (rows) => rows.filter((r) => sortKey(r) === null).length;
  const poolKey = (r) => [r.en || 'unattributed', r.t0a, r.t1a];
  function group(rows) {
    const pools = new Map();
    for (const r of order(rows)) {
      const k = poolKey(r).join(' ');
      if (!pools.has(k)) pools.set(k, { key: poolKey(r), rows: [] });
      pools.get(k).rows.push(r);
    }
    return [...pools.values()];
  }
  function sizeMatch(a, b, tol) {
    const a0a = toF(a.a0), a0b = toF(b.a0);
    if (a0a == null || a0b == null || a0a <= 0) return false;
    return Math.abs(a0b - a0a) / a0a <= tol;
  }
  function legsMatch(a, b, tol) {
    return a.ma != null && a.ma === b.ma && toInt(a.h) != null && toInt(a.h) === toInt(b.h)
      && ['buy', 'sell'].includes(side(a)) && ['buy', 'sell'].includes(side(b)) && side(a) !== side(b)
      && sizeMatch(a, b, tol);
  }
  function take(first, second) {
    const a1f = toF(first.a1), a1s = toF(second.a1);
    if (a1f == null || a1s == null) return null;
    return side(first) === 'buy' ? a1s - a1f : a1f - a1s;
  }
  function middlemen(rows, tol = SIZE_TOL, maxVictims = MAX_VICTIMS) {
    const n = rows.length, consumed = new Set(), rt = [], sw = [];
    for (let i = 0; i < n; i++) {
      if (consumed.has(i)) continue;
      const a = rows[i];
      if (a.ma == null || !['buy', 'sell'].includes(side(a))) continue;
      const h = toInt(a.h);
      let k = null; const between = [];
      for (let j = i + 1; j < n; j++) {
        const r = rows[j];
        if (toInt(r.h) !== h) break;
        if (r.ma === a.ma) { k = j; break; }
        between.push(j);
      }
      if (k === null || consumed.has(k) || !legsMatch(a, rows[k], tol)) continue;
      const b = rows[k], tk = take(a, b), victims = between.map((j) => rows[j]);
      const isSandwich = between.length >= 1 && between.length <= maxVictims
        && between.every((j) => !consumed.has(j) && side(rows[j]) === side(a)) && tk != null && tk > 0;
      if (isSandwich) sw.push({ i, k, ma: a.ma, h: a.h, victims, legs: [a, b], take_quote: tk });
      else rt.push({ i, k, ma: a.ma, h: a.h, same_tx: a.tx != null && a.tx === b.tx, between: between.length, take_quote: tk, legs: [a, b] });
      consumed.add(i); consumed.add(k);
    }
    const organic = rows.filter((_, idx) => !consumed.has(idx));
    return { rt, sw, organic };
  }
  function wallets(matches) { const seen = new Set(), out = []; for (const m of matches) if (!seen.has(m.ma)) { seen.add(m.ma); out.push(m.ma); } return out; }

  // ── cost ───────────────────────────────────────────────────────────────────
  function price(r) { const a0 = toF(r.a0), a1 = toF(r.a1); return a0 == null || a1 == null || a0 <= 0 ? null : a1 / a0; }
  function quoteToFill(rows) {
    const out = []; let prev = null;
    rows.forEach((r, idx) => {
      const q = price(r); if (q == null || q <= 0) return;
      if (prev != null && prev > 0) {
        const tp = side(r);
        if (tp === 'buy') out.push({ idx, bps: (q / prev - 1) * BPS, tp, q, q_prev: prev });
        else if (tp === 'sell') out.push({ idx, bps: (1 - q / prev) * BPS, tp, q, q_prev: prev });
        else { prev = q; return; }
      }
      prev = q;
    });
    return out;
  }
  function percentile(values, p) {
    if (!values.length) return null;
    const o = [...values].sort((a, b) => a - b);
    const rank = Math.max(1, Math.min(o.length, Math.ceil(p / 100 * o.length - 1e-9))); // ceil: see cost.py
    return o[rank - 1];
  }
  const round2 = (v) => v == null ? null : Math.round(v * 100) / 100;
  const round4 = (v) => v == null ? null : Math.round(v * 10000) / 10000;
  function spanHours(rows) { const ts = rows.map((r) => toF(r.ts)).filter((t) => t != null); return ts.length < 2 ? 0 : (Math.max(...ts) - Math.min(...ts)) / 3600000; }
  function example(rows, rt, sw, organicQ2f, organic) {
    if (rt.length || sw.length) {
      const m = rt.length ? rt[0] : sw[0], kind = rt.length ? 'round-trip' : 'sandwich', h = toInt(m.h);
      return { kind, h: m.h, rows: rows.filter((r) => toInt(r.h) === h), highlight: m.legs.map((r) => r.lgid), victims: (m.victims || []).map((r) => r.lgid), take_quote: m.take_quote, same_tx: !!m.same_tx };
    }
    for (const e of organicQ2f) {
      const r = organic[e.idx], p = organic[e.idx - 1];
      if (toInt(r.h) === toInt(p.h)) return { kind: 'organic', h: r.h, rows: [p, r], highlight: [r.lgid], victims: [], bps: e.bps, tp: e.tp };
    }
    return null;
  }
  function poolRow(key, rows, rt, sw, organic) {
    const vol = rows.reduce((s, r) => s + (toF(r.v) || 0), 0);
    const rtLegs = rt.flatMap((m) => m.legs);
    const rtVol = rtLegs.reduce((s, r) => s + (toF(r.v) || 0), 0);
    const oq = quoteToFill(organic), nq = quoteToFill(rows);
    const ob = oq.map((e) => e.bps), nb = nq.map((e) => e.bps);
    return {
      key, venue: key[0], quote: (rows[0] && rows[0].t1s) || key[2],
      n: rows.length, n_organic: organic.length, makers: new Set(rows.map((r) => r.ma)).size,
      volume_usd: round2(vol), span_hours: round2(spanHours(rows)),
      round_trips: { pairs: rt.length, wallets: wallets(rt), share_prints: rows.length ? round4(rtLegs.length / rows.length) : 0, share_volume: vol ? round4(rtVol / vol) : 0, same_tx_share: rt.length ? round4(rt.filter((m) => m.same_tx).length / rt.length) : null, volume_usd: round2(rtVol) },
      sandwiches: { count: sw.length, wallets: wallets(sw), victims: sw.reduce((s, m) => s + m.victims.length, 0) },
      q2f: { n: ob.length, p50_bps: ob.length ? round2(percentile(ob, 50)) : null, p90_bps: ob.length ? round2(percentile(ob, 90)) : null },
      naive: { n: nb.length, p50_bps: nb.length ? round2(percentile(nb, 50)) : null, p90_bps: nb.length ? round2(percentile(nb, 90)) : null },
      example: example(rows, rt, sw, oq, organic),
    };
  }

  // ── recommend ──────────────────────────────────────────────────────────────
  function capPct(p90) { if (p90 == null) return null; const steps = Math.ceil(Math.max(p90, 0) / (CAP_STEP_PCT * 100)); return Math.round(Math.max(steps, 1) * CAP_STEP_PCT * 100) / 100; }
  function route(rows) {
    const c = rows.filter((r) => r.n_organic >= MIN_ORGANIC && r.q2f.p90_bps != null);
    if (!c.length) return { pool: null, venue: null, quote: null, p90_bps: null, cap_pct: null, candidates: 0, why: 'no pool has ≥ 50 organic prints in this window — pull more pages rather than lower the bar' };
    const best = c.reduce((a, b) => (b.q2f.p90_bps < a.q2f.p90_bps || (b.q2f.p90_bps === a.q2f.p90_bps && b.n_organic > a.n_organic)) ? b : a);
    return { pool: best.key, venue: best.venue, quote: best.quote, p90_bps: best.q2f.p90_bps, cap_pct: capPct(best.q2f.p90_bps), candidates: c.length, why: RULE };
  }
  function compute(prints) {
    const pools = group(prints).map((g) => { const { rt, sw, organic } = middlemen(g.rows); return poolRow(g.key, g.rows, rt, sw, organic); })
      .sort((a, b) => b.n - a.n);
    const all = order(prints);
    return { pools, decision: route(pools), window: { prints: prints.length, span_hours: round2(spanHours(prints)), first_block: all.length ? all[0].h : null, last_block: all.length ? all[all.length - 1].h : null, unplaceable: unplaceable(prints) } };
  }

  const engine = { order, group, middlemen, price, quoteToFill, percentile, poolRow, route, compute, capPct, RULE };
  if (typeof module !== 'undefined' && module.exports) { module.exports = engine; return; }
  if (typeof document === 'undefined') return;

  // ── the page ───────────────────────────────────────────────────────────────
  const $ = (id) => document.getElementById(id);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const short = (a, n = 6) => { a = String(a || ''); return a.length > n + 4 ? a.slice(0, n) + '…' + a.slice(-4) : a; };
  const usd = (v) => v == null ? '—' : v >= 1e6 ? '$' + (v / 1e6).toFixed(1) + 'M' : v >= 1e3 ? '$' + Math.round(v / 1e3) + 'k' : '$' + Math.round(v);
  const bps = (v) => v == null ? '—' : v.toFixed(1);
  const data = JSON.parse($('receipts').textContent);
  let current = null, sortKeyName = 'p90', sortAsc = true, live = false, generation = 0;

  function sortRows(pools) {
    const get = { pool: (p) => p.venue + p.quote, n: (p) => p.n, n_organic: (p) => p.n_organic, rt: (p) => p.round_trips.share_volume, sw: (p) => p.sandwiches.count, p90: (p) => p.q2f.p90_bps == null ? Infinity : p.q2f.p90_bps, tax: (p) => (p.buy_tax || 0) + (p.sell_tax || 0), liq: (p) => p.liq_usd == null ? -1 : p.liq_usd }[sortKeyName];
    return [...pools].sort((a, b) => { const x = get(a), y = get(b); const c = typeof x === 'string' ? x.localeCompare(y) : x - y; return sortAsc ? c : -c; });
  }
  function heroPool(result) {
    // the pool the headline is about: widest round-trip share, else most sandwiches, else the routed pool
    const withRt = result.pools.filter((p) => p.round_trips.pairs);
    if (withRt.length) return withRt.reduce((a, b) => b.round_trips.share_volume > a.round_trips.share_volume ? b : a);
    const withSw = result.pools.filter((p) => p.sandwiches.count);
    if (withSw.length) return withSw.reduce((a, b) => b.sandwiches.count > a.sandwiches.count ? b : a);
    return result.pools.find((p) => JSON.stringify(p.key) === JSON.stringify(result.decision.pool)) || result.pools[0];
  }
  function renderTable(result) {
    const routed = JSON.stringify(result.decision.pool), shown = JSON.stringify(heroPool(result).key);
    const rows = sortRows(result.pools);
    $('tbody').innerHTML = rows.map((p) => {
      const rt = p.round_trips, sw = p.sandwiches, i = result.pools.indexOf(p);
      const cls = [JSON.stringify(p.key) === routed ? 'routed' : '', rt.pairs || sw.count ? 'middle' : ''].join(' ').trim();
      let name = esc(p.venue) + ' / ' + esc(p.quote);
      if (p.pools_merged > 1) name += '<small>×' + p.pools_merged + '</small>';
      if (JSON.stringify(p.key) === routed) name += '<small class="mark">◀ route</small>';
      const rtTxt = rt.pairs ? rt.pairs + ' · ' + rt.wallets.length + ' wallet' + (rt.wallets.length !== 1 ? 's' : '') + ' · ' + (rt.share_volume * 100).toFixed(1) + '%' : '—';
      const tax = p.buy_tax != null && p.sell_tax != null ? p.buy_tax.toFixed(0) + ' / ' + p.sell_tax.toFixed(0) : '—';
      return '<tr class="' + cls + '" data-i="' + i + '" tabindex="0" aria-selected="' + (JSON.stringify(p.key) === shown) + '">'
        + '<td class="pool">' + name + '</td><td class="mono">' + p.n + '</td><td class="mono">' + p.n_organic + '</td>'
        + '<td class="mono rt' + (rt.pairs ? '' : ' none') + '">' + rtTxt + '</td><td class="mono sw' + (sw.count ? '' : ' none') + '">' + sw.count + '</td>'
        + '<td class="mono q2f">' + bps(p.q2f.p50_bps) + ' / ' + bps(p.q2f.p90_bps) + ' bps</td><td class="mono">' + tax + '</td><td class="mono">' + usd(p.liq_usd) + '</td></tr>';
    }).join('');
    document.querySelectorAll('#pools th').forEach((th) => { if (th.dataset.k === sortKeyName) th.setAttribute('aria-sort', sortAsc ? 'ascending' : 'descending'); else th.removeAttribute('aria-sort'); });
  }
  function renderHero(result) {
    const hero = $('hero');
    const withRt = result.pools.filter((p) => p.round_trips.pairs);
    const withSw = result.pools.filter((p) => p.sandwiches.count);
    if (withRt.length) {
      const p = withRt.reduce((a, b) => b.round_trips.share_volume > a.round_trips.share_volume ? b : a), rt = p.round_trips;
      hero.className = 'hero middle';
      $('share').textContent = (rt.share_volume * 100).toFixed(1) + '%';
      $('claim').innerHTML = 'of ' + esc(p.venue) + ' / ' + esc(p.quote) + ' volume is <em>' + rt.wallets.length + ' wallet' + (rt.wallets.length !== 1 ? 's' : '') + '</em> buying back what they just sold' + ((rt.same_tx_share || 0) >= 0.5 ? ', in the same transaction' : '') + '.';
      $('support').innerHTML = rt.pairs + ' round-trips · ' + p.sandwiches.count + ' sandwiches in ' + p.n + ' prints. Take the legs out and an organic fill here pays <b>' + bps(p.q2f.p50_bps) + ' bps</b> median; the raw tape says ' + bps(p.naive.p50_bps) + '.';
      return;
    }
    if (withSw.length) {
      const p = withSw.reduce((a, b) => b.sandwiches.count > a.sandwiches.count ? b : a);
      hero.className = 'hero middle';
      $('share').textContent = p.sandwiches.count + ' sandwich' + (p.sandwiches.count !== 1 ? 'es' : '');
      $('claim').innerHTML = 'in ' + esc(p.venue) + ' / ' + esc(p.quote) + ' — <em>' + p.sandwiches.victims + ' fill' + (p.sandwiches.victims !== 1 ? 's' : '') + ' front-run</em> inside one block, by ' + p.sandwiches.wallets.map((w) => short(w)).join(', ') + '.';
      $('support').innerHTML = 'No round-trips. An organic fill here pays <b>' + bps(p.q2f.p50_bps) + ' bps</b> median, p90 ' + bps(p.q2f.p90_bps) + '.';
      return;
    }
    const priced = result.pools.filter((p) => p.n_organic >= MIN_ORGANIC && (p.q2f.p50_bps || 0) > 0);
    if (priced.length >= 2) {
      const lo = priced.reduce((a, b) => b.q2f.p50_bps < a.q2f.p50_bps ? b : a), hi = priced.reduce((a, b) => b.q2f.p50_bps > a.q2f.p50_bps ? b : a);
      hero.className = 'hero spread';
      $('share').textContent = (hi.q2f.p50_bps / lo.q2f.p50_bps).toFixed(1) + '×';
      $('claim').innerHTML = 'more per fill in <em>' + esc(hi.venue) + ' / ' + esc(hi.quote) + '</em> than in ' + esc(lo.venue) + ' / ' + esc(lo.quote) + ' — same token, same window.';
      $('support').innerHTML = 'No round-trips and no sandwiches — the middleman is the pool itself. ' + bps(lo.q2f.p50_bps) + ' vs ' + bps(hi.q2f.p50_bps) + ' bps median quote-to-fill.';
      return;
    }
    hero.className = 'hero none';
    $('share').textContent = '0';
    $('claim').textContent = 'middlemen found in this window — every print organic; the cap is the pool\'s own p90.';
    $('support').textContent = result.window.prints + ' prints, every one organic.';
  }
  function renderRoute(result) {
    const d = result.decision;
    if (!d.pool) { $('routeline').textContent = 'no route — ' + d.why; $('routerule').textContent = RULE; return; }
    $('routeline').textContent = '▶ route via ' + d.venue + ' / ' + d.quote + ' · cap slippage at ' + d.cap_pct.toFixed(2) + ' %';
    $('routerule').textContent = 'rule: ' + RULE + ' · organic p90 here ' + bps(d.p90_bps) + ' bps · ' + d.candidates + ' candidate pool' + (d.candidates !== 1 ? 's' : '');
  }
  function renderRows(result, pool) {
    const ex = pool.example, txuf = (data.platforms[result.platform] || {}).txuf;
    $('rowstitle').textContent = pool.venue + ' / ' + pool.quote + ' — raw rows' + (ex ? ' (' + ex.kind + ')' : '');
    if (!ex) { $('rowscap').textContent = 'this pool has a single print in the window; nothing to compare'; $('rowlist').innerHTML = ''; $('arith').innerHTML = ''; $('rawpre').textContent = '[]'; return; }
    const legs = new Set(ex.highlight), victims = new Set(ex.victims || []);
    const what = { 'round-trip': 'the block that holds the first round-trip — both legs in orange', sandwich: 'the block that holds the first sandwich — the legs in orange, the victim in red', organic: 'two consecutive organic prints in one block — the bps between them, computed inline' }[ex.kind];
    $('rowscap').innerHTML = 'block ' + esc(ex.h) + ' · ' + what + ' · endpoint <span class="mono">/public-api/v1/dex/tokens/transactions</span>' + (result.tape ? ' · <a href="' + esc(data.repo || REPO) + '/blob/main/' + esc(result.tape) + '" target="_blank" rel="noopener noreferrer">the whole tape ↗</a>' : live ? ' · fetched live through /api/swaps just now' : '');
    $('rowlist').innerHTML = '<table><thead><tr><th>lgid</th><th>maker</th><th>side</th><th>a0 (base)</th><th>a1 (quote)</th><th>a1 / a0</th><th>tx</th></tr></thead><tbody>'
      + ex.rows.slice(0, 14).map((r) => {
        const cls = legs.has(r.lgid) ? 'leg' : victims.has(r.lgid) ? 'victim' : ex.kind === 'organic' ? 'fill' : '';
        const q = price(r), tx = r.tx || '';
        const link = txuf && tx ? '<a href="' + esc(txuf.replace('%s', tx)) + '" target="_blank" rel="noopener noreferrer" class="mono">' + esc(short(tx, 8)) + ' ↗</a>' : '<span class="mono">' + esc(short(tx, 8)) + '</span>';
        return '<tr class="' + cls + '"><td class="mono">' + esc(r.lgid) + '</td><td class="mono" title="' + esc(r.ma) + '">' + esc(short(r.ma, 10)) + '</td><td>' + esc(r.tp) + '</td>'
          + (q == null ? '<td colspan="4">unpriceable row</td>' : '<td class="mono">' + Number(r.a0).toLocaleString('en-US', { minimumFractionDigits: 4, maximumFractionDigits: 4 }) + '</td><td class="mono">' + Number(r.a1).toLocaleString('en-US', { minimumFractionDigits: 6, maximumFractionDigits: 6 }) + '</td><td class="mono">' + q.toExponential(4) + '</td><td>' + link + '</td>') + '</tr>';
      }).join('') + '</tbody></table>';
    const a = ex.rows.find((r) => r.lgid === ex.highlight[0]), b = ex.rows.find((r) => r.lgid === ex.highlight[ex.highlight.length - 1]);
    const lines = [];
    if (ex.arithmetic) {
      lines.push(...ex.arithmetic); // the Python engine's own lines, committed with the receipt
    } else if (ex.kind === 'organic') {
      const p = ex.rows[0], r = ex.rows[1];
      lines.push('previous print  lgid ' + p.lgid + '  ' + side(p) + '  a1/a0 = ' + price(p), 'this print      lgid ' + r.lgid + '  ' + side(r) + '  a1/a0 = ' + price(r), (ex.tp === 'buy' ? 'q/q_prev - 1' : '1 - q/q_prev') + ' = ' + ex.bps.toFixed(1) + ' bps adverse');
    } else if (a && b) {
      const d = Math.abs(toF(b.a0) - toF(a.a0)) / toF(a.a0);
      lines.push('leg 1  lgid ' + a.lgid + '  ' + a.ma + '  ' + side(a) + '  a1/a0 = ' + a.a1 + ' / ' + a.a0 + ' = ' + price(a), 'leg 2  lgid ' + b.lgid + '  ' + b.ma + '  ' + side(b) + '  a1/a0 = ' + b.a1 + ' / ' + b.a0 + ' = ' + price(b), 'same wallet · same block ' + ex.h + (ex.same_tx ? ' · same tx' : '') + ' · |da0| / a0 = ' + d.toFixed(4) + ' <= 0.05 -> ' + ex.kind);
      if (ex.kind === 'sandwich') lines.push((ex.victims || []).length + ' other maker(s) printed ' + side(a) + ' between the legs · take ' + Number(ex.take_quote).toPrecision(4) + ' ' + pool.quote);
    }
    $('arith').innerHTML = lines.map((l) => '<li>' + esc(l) + '</li>').join('');
    $('rawpre').textContent = JSON.stringify(ex.rows.slice(0, 14), Object.keys(ex.rows[0] || {}).sort(), 1);
  }
  function renderReceipt(result) {
    if (!result.calls_n && !result.first_url) return;
    const items = [['endpoint', '<span class="mono">/public-api/v1/dex/tokens/transactions</span>'], ['calls', result.calls_n + (live ? ' · through /api/swaps, just now' : '')], ['credits used', '<span class="mono">0</span> — none, keyless'], ['captured', '<span class="mono">' + esc(result.captured_utc) + '</span>' + (result.wall_s != null ? ' · ' + result.wall_s + ' s wall clock' : '')], ['first page sha256', '<span class="mono">' + esc(result.first_sha256 || '— (browser fetches carry no hash)') + '</span>'], ['first request', result.first_url ? '<a class="mono" href="' + esc(result.first_url) + '" target="_blank" rel="noopener noreferrer">' + esc(result.first_url) + '</a>' : '—'], ['re-derive', '<span class="mono">python3 scripts/verify_tape.py</span> · <a href="evidence.html">every call →</a>']];
    $('receipt-grid').innerHTML = items.map(([k, v]) => '<div><div class="k">' + k + '</div><div class="v">' + v + '</div></div>').join('');
  }
  function show(result) {
    current = result; generation++;
    const w = result.window;
    $('context').innerHTML = '<b>' + esc(result.symbol) + '</b> · ' + esc(result.platform.charAt(0).toUpperCase() + result.platform.slice(1)) + ' · last ' + w.prints + ' prints · ' + w.span_hours + ' h · blocks ' + esc(w.first_block) + '–' + esc(w.last_block) + ' · ' + (live ? 'fetched live just now · keyless' : 'captured ' + esc(String(result.captured_utc).replace('T', ' ').replace('Z', ' UTC')) + ' · keyless') + (live ? '' : ' · <span title="' + esc(data.hero.rule || '') + '">' + (result.symbol === data.hero.symbol ? 'chosen by rule: ' + esc(data.hero.rule || '') : 'pinned watchlist') + '</span>');
    renderHero(result); renderTable(result); renderRoute(result);
    if (result.pools.length) renderRows(result, heroPool(result));
    renderReceipt(result);
    document.querySelectorAll('#tokens button').forEach((b) => b.setAttribute('aria-pressed', String(!live && data.receipts[b.dataset.i] && data.receipts[b.dataset.i].symbol === result.symbol)));
  }
  // row selection -> the raw-rows panel
  $('tbody').addEventListener('click', (e) => { const tr = e.target.closest('tr'); if (!tr || !current) return; select(tr); });
  $('tbody').addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { const tr = e.target.closest('tr'); if (tr) { e.preventDefault(); select(tr); } } });
  function select(tr) {
    document.querySelectorAll('#tbody tr').forEach((r) => r.setAttribute('aria-selected', 'false'));
    tr.setAttribute('aria-selected', 'true');
    renderRows(current, current.pools[+tr.dataset.i]);
    $('rows').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
  // sortable headers
  document.querySelectorAll('#pools th').forEach((th) => th.addEventListener('click', () => { const k = th.dataset.k; if (sortKeyName === k) sortAsc = !sortAsc; else { sortKeyName = k; sortAsc = k !== 'rt' && k !== 'sw' && k !== 'liq' && k !== 'n'; } if (current) renderTable(current); }));
  // token buttons: switch tables with zero requests
  $('tokens').addEventListener('click', (e) => { const b = e.target.closest('button'); if (!b) return; live = false; show(data.receipts[+b.dataset.i]); $('mode').textContent = 'committed run'; $('mode').className = 'chip ok'; $('status').textContent = ''; });
  // the initial view is the server-rendered hero; hydrate `current` so clicks work
  current = data.receipts.find((r) => r.symbol === data.hero.symbol) || data.receipts[0];
  // count the headline share up from 0 - one animation, the mechanism in two seconds
  (function countUp() {
    const el = $('share'), target = parseFloat(el.dataset.target), text = el.textContent;
    if (!Number.isFinite(target) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const suffix = text.replace(/^[0-9.]+/, ''), start = performance.now(), dur = 1400, gen = generation;
    (function tick(now) { if (gen !== generation) return; const t = Math.min(1, (now - start) / dur), v = target * (1 - Math.pow(1 - t, 3)); el.textContent = v.toFixed(1) + suffix; if (t < 1) requestAnimationFrame(tick); else el.textContent = text; })(start);
  })();

  // ── the paste box: live, keyless, through /api/swaps ───────────────────────
  async function pull(platform, address, pages, onProgress) {
    const seen = new Set(), out = []; let cursor = null, n = 0, firstUrl = null;
    for (let p = 0; p < pages; p++) {
      const qs = new URLSearchParams({ platform, address, limit: '100' }); if (cursor) qs.set('lastId', cursor);
      onProgress(p + 1, pages);
      const res = await fetch(API_BASE + '/api/swaps?' + qs.toString());
      const body = await res.json().catch(() => ({}));
      if (!res.ok || !body.ok) { const err = new Error(body.error || ('HTTP ' + res.status)); err.status = res.status; err.hint = body.hint; err.pages = n; throw err; }
      n++; if (!firstUrl) firstUrl = body.source;
      const dataBlk = (body.raw && body.raw.data) || {}; const batch = dataBlk.swaps || [];
      if (!batch.length) break;
      let fresh = 0;
      for (const s of batch) { const k = s.tx + ' ' + s.lgid; if (seen.has(k)) continue; seen.add(k); out.push(s); fresh++; }
      if (!fresh) break;
      cursor = dataBlk.lastId; if (!cursor) break;
    }
    return { prints: out, pages: n, firstUrl };
  }
  $('paste').addEventListener('submit', async (e) => {
    e.preventDefault();
    const address = $('addr').value.trim(), platform = $('platform').value;
    if (!address) { $('status').textContent = 'paste a token contract address first'; return; }
    const go = $('go'), status = $('status'), mode = $('mode');
    go.disabled = true; mode.textContent = 'fetching'; mode.className = 'chip busy';
    const t0 = performance.now();
    try {
      const { prints, pages, firstUrl } = await pull(platform, address, 8, (i, n) => { status.textContent = 'page ' + i + ' of ' + n + ' - keyless, through /api/swaps'; });
      if (!prints.length) throw Object.assign(new Error('no swaps returned for that address on ' + platform), { status: 200 });
      const result = compute(prints);
      result.symbol = (prints[0].t0s || 'TOKEN'); result.platform = platform; result.address = address;
      result.captured_utc = new Date().toISOString().replace(/\.\d+Z$/, 'Z'); result.calls_n = pages; result.first_url = firstUrl; result.first_sha256 = null; result.wall_s = Math.round((performance.now() - t0) / 100) / 10;
      result.pools.forEach((p) => { p.buy_tax = null; p.sell_tax = null; p.liq_usd = null; p.pools_merged = null; });
      live = true; show(result);
      status.textContent = prints.length + ' prints in ' + pages + ' page' + (pages !== 1 ? 's' : '') + ', ' + result.wall_s + ' s, 0 credits. Taxes and liquidity are left blank on the live path - the CLI fills them.';
      mode.textContent = 'live · keyless'; mode.className = 'chip ok';
      $('hero').scrollIntoView({ behavior: 'smooth', block: 'start' });
    } catch (err) {
      mode.textContent = 'HTTP ' + (err.status || '-'); mode.className = 'chip err';
      const cmd = 'python3 scripts/middleman.py --address ' + address + ' --platform ' + platform + ' --pages 8';
      status.innerHTML = (err.status === 429 ? 'HTTP 429 - CoinMarketCap\'s anonymous tier is rate-limited per IP, and every visitor of this page shares one. ' + (err.pages ? err.pages + ' page(s) landed before it tripped. ' : '') + 'Run the same measurement from a fresh clone, keyless:' : esc(err.message) + '. Run it locally, keyless:') + '<span class="cmd">' + esc(cmd) + '</span>';
    } finally { go.disabled = false; }
  });

  // ── the family layer (LANDING_DESIGN.md §7): sticky header, reveal on scroll, the h1
  //    count-up, the block's one animation, the folds, the copy button. Every motion here
  //    is a no-op under prefers-reduced-motion — the CSS carries the final state there. ──
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const top = $('top');
  if (top) {
    const onScroll = () => top.classList.toggle('scrolled', window.scrollY > 8);
    window.addEventListener('scroll', onScroll, { passive: true });
    requestAnimationFrame(onScroll);
  }
  const io = 'IntersectionObserver' in window
    ? new IntersectionObserver((es) => { es.forEach((e) => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } }); }, { rootMargin: '0px 0px -8% 0px', threshold: 0.08 })
    : null;
  document.querySelectorAll('.reveal').forEach((el) => { if (io) io.observe(el); else el.classList.add('in'); });
  // every svg.block gets .go (a project with a phone variant has two); the visible one is observed
  const blocks = [...document.querySelectorAll('svg.block')], block = blocks.find((b) => b.getClientRects().length) || blocks[0];
  const release = () => blocks.forEach((b) => b.classList.add('go'));
  // safety: nothing stays hidden if the observer never fires (print, full-page capture, odd embeds)
  setTimeout(() => { document.querySelectorAll('.reveal').forEach((el) => el.classList.add('in', 'now')); if (block) release(); }, 2500);
  if (block) {
    if (reduce || !('IntersectionObserver' in window)) release();
    else { const bo = new IntersectionObserver((es) => { es.forEach((e) => { if (e.isIntersecting) { release(); bo.disconnect(); } }); }, { threshold: 0.35 }); bo.observe(block); }
  }
  // the headline number counts up once, when it is in view; the span reserves its width in CSS
  const big = document.querySelector('h1 [data-count]');
  if (big && !reduce && 'IntersectionObserver' in window) {
    const target = parseFloat(big.dataset.count), suffix = big.textContent.replace(/^[0-9.]+/, ''), dec = (big.dataset.count.split('.')[1] || '').length;
    let t0 = null; const dur = 1100;
    const tick = (ts) => { if (!t0) t0 = ts; let p = Math.min(1, (ts - t0) / dur); p = 1 - Math.pow(1 - p, 3); big.textContent = (target * p).toFixed(dec) + suffix; if (p < 1) requestAnimationFrame(tick); else big.textContent = big.dataset.count + suffix; };
    const co = new IntersectionObserver((es) => { if (es[0].isIntersecting) { requestAnimationFrame(tick); co.disconnect(); } }, { threshold: 0.5 });
    co.observe(big);
  }
  // folds: open first, then release the track (0fr → 1fr); on close run the track back and only
  // then close the element. Under reduced motion the native snap is the whole behaviour.
  if (!reduce) document.querySelectorAll('details').forEach((d) => {
    const sum = d.querySelector(':scope > summary'), fold = d.querySelector(':scope > .fold');
    if (!sum || !fold) return;
    d.classList.add('fx');
    let closing = null;
    const settle = () => { if (closing) { clearTimeout(closing); closing = null; d.open = false; } };
    fold.addEventListener('transitionend', (e) => { if (e.target === fold && !d.classList.contains('is-open')) settle(); });
    sum.addEventListener('click', (e) => {
      e.preventDefault();
      if (d.open && !closing) { d.classList.remove('is-open'); closing = setTimeout(settle, 320); }
      else if (!d.open) { d.open = true; void fold.offsetHeight; d.classList.add('is-open'); }
    });
    d.addEventListener('toggle', () => {
      if (d.open && !d.classList.contains('is-open') && !closing) { void fold.offsetHeight; d.classList.add('is-open'); }
      if (!d.open) d.classList.remove('is-open');
    });
  });
  // copy the reproduce command
  document.querySelectorAll('button.copy[data-copy]').forEach((btn) => btn.addEventListener('click', () => {
    const done = () => { btn.textContent = 'copied'; btn.classList.add('done'); setTimeout(() => { btn.textContent = 'copy'; btn.classList.remove('done'); }, 1600); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(btn.dataset.copy).then(done, done); else done();
  }));
})();
