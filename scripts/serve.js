#!/usr/bin/env node
// Serve site/ and the two functions under api/ locally, the way Vercel routes them.
//
//     node scripts/serve.js            # http://localhost:8101
//     PORT=8101 node scripts/serve.js
//
// No dependencies. Exists so the paste box can be exercised end to end from a fresh clone —
// the browser cannot call CoinMarketCap directly (no Access-Control-Allow-Origin), so /api/swaps
// is the same keyless passthrough the deployment runs.
const http = require('http');
const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SITE = path.join(ROOT, 'site');
const PORT = Number(process.env.PORT || 8101);
const TYPES = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.md': 'text/markdown; charset=utf-8', '.css': 'text/css' };

http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');
  if (url.pathname.startsWith('/api/')) {
    const name = url.pathname.slice(5).replace(/[^a-z_]/g, '');
    const file = path.join(ROOT, 'api', name + '.js');
    if (!fs.existsSync(file)) { res.statusCode = 404; return res.end('{"ok":false,"error":"no such function"}'); }
    req.query = Object.fromEntries(url.searchParams.entries());
    process.chdir(ROOT);
    try { await require(file)(req, res); } catch (err) { res.statusCode = 500; res.end(JSON.stringify({ ok: false, error: String(err) })); }
    return;
  }
  let rel = decodeURIComponent(url.pathname);
  if (rel === '/') rel = '/index.html';
  if (!path.extname(rel) && fs.existsSync(path.join(SITE, rel + '.html'))) rel += '.html'; // cleanUrls
  const file = path.normalize(path.join(SITE, rel));
  if (!file.startsWith(SITE) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) { res.statusCode = 404; return res.end('not found'); }
  res.setHeader('Content-Type', TYPES[path.extname(file)] || 'application/octet-stream');
  fs.createReadStream(file).pipe(res);
}).listen(PORT, () => console.log('middleman · http://localhost:' + PORT + '  (site/ + api/, keyless)'));
