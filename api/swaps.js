// Keyless passthrough for CoinMarketCap's per-swap feed, with the one header CMC omits.
//
// CMC sends Access-Control-Allow-Headers, -Methods and -Max-Age on /public-api but not
// Access-Control-Allow-Origin, so a browser cannot read the response (FEEDBACK.md #1). This
// function's whole job is to fetch the identical keyless URL and hand the body back untouched
// with that header and a 60 s CDN cache, so ten judges pasting one token are one upstream call.
// It holds no secret: there is no key anywhere in this deployment.
const BASE = 'https://pro-api.coinmarketcap.com/public-api/v1/dex/tokens/transactions';
const PLATFORMS = new Set(['ethereum', 'bsc', 'solana']);
const ADDRESS = /^[A-Za-z0-9]{20,64}$/; // 0x + 40 hex on EVM chains, base58 on Solana
const CURSOR = /^[A-Za-z0-9+/=_-]{1,200}$/;

module.exports = async (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  if (req.method === 'OPTIONS') { res.statusCode = 204; return res.end(); }
  const q = req.query || {};
  const platform = String(q.platform || 'ethereum').toLowerCase();
  const address = String(q.address || '');
  const lastId = q.lastId ? String(q.lastId) : '';
  if (!PLATFORMS.has(platform) || !ADDRESS.test(address) || (lastId && !CURSOR.test(lastId))) {
    res.statusCode = 400;
    return res.end(JSON.stringify({ ok: false, status: 400, error: 'platform must be ethereum|bsc|solana and address a contract address' }));
  }
  const url = new URL(BASE);
  url.searchParams.set('platform', platform);
  url.searchParams.set('address', address);
  url.searchParams.set('limit', '100');
  if (lastId) url.searchParams.set('lastId', lastId);
  const fetched_utc = new Date().toISOString().replace(/\.\d+Z$/, 'Z');
  let upstream;
  try {
    upstream = await fetch(url.toString(), { headers: { Accept: 'application/json' } });
  } catch (err) {
    res.statusCode = 502;
    return res.end(JSON.stringify({ ok: false, status: 502, error: 'could not reach CoinMarketCap: ' + err.message, fetched_utc }));
  }
  const text = await upstream.text();
  let raw = null;
  try { raw = JSON.parse(text); } catch (_) { raw = null; }
  const source = url.toString();
  if (!upstream.ok) {
    const status = (raw && raw.status) || {};
    const error = 'HTTP ' + upstream.status + (status.error_code ? ' (error ' + status.error_code + ')' : '') + (status.error_message ? ': ' + status.error_message : '');
    res.statusCode = upstream.status;
    res.setHeader('Cache-Control', 'no-store');
    return res.end(JSON.stringify({ ok: false, status: upstream.status, error, source, fetched_utc,
      hint: 'python3 scripts/middleman.py --address ' + address + ' --platform ' + platform + ' --pages 8' }));
  }
  res.statusCode = 200;
  res.setHeader('Cache-Control', 'public, s-maxage=60, stale-while-revalidate=120');
  res.end(JSON.stringify({ ok: true, source, status: upstream.status, fetched_utc, credit_count: 0, raw }));
};
