// Liveness: the deploy is not a frozen screenshot. Returns the server's clock, the capture
// time of the receipts the page was rendered from, and the engine version. No upstream call,
// so it never spends the anonymous quota judges share.
const fs = require('fs');
const path = require('path');

module.exports = (req, res) => {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Content-Type', 'application/json; charset=utf-8');
  res.setHeader('Cache-Control', 'no-store');
  let census = null;
  try {
    census = JSON.parse(fs.readFileSync(path.join(process.cwd(), 'docs', 'proof', 'census.json'), 'utf8'));
  } catch (_) { census = null; }
  res.statusCode = 200;
  res.end(JSON.stringify({
    ok: true,
    now_utc: new Date().toISOString().replace(/\.\d+Z$/, 'Z'),
    receipts_captured_utc: census ? census.captured_utc : null,
    hero: census ? { symbol: census.hero.symbol, fired: census.hero.fired } : null,
    census: census ? { tokens: census.tokens, prints: census.prints, sandwiches: census.sandwiches, round_trips: census.round_trip_pairs } : null,
    keyless: true,
    proxy: '/api/swaps?platform=ethereum&address=0x…[&lastId=…]',
  }));
};
