// Custom server (see node_modules/next/dist/docs/.../custom-server.md) — the
// only way to get each visitor's real IP to the backend. next.config.mjs's
// rewrites() proxy every /api/* request to the backend at 127.0.0.1:8082;
// Next's internal proxy (node_modules/next/dist/server/lib/router-utils/
// proxy-request.js) only forwards an x-forwarded-host header, never the
// client's real IP, and Next 16 has no NextRequest.ip for a self-hosted
// deployment like this one. So we read it off the raw socket here, before
// Next (and its rewrite proxy) ever sees the request, and forward it as
// x-forwarded-for — main.py's /api/log-visit route reads that header.
const { createServer } = require('http');
const next = require('next');

const port = parseInt(process.env.PORT || '3000', 10);
const dev = process.env.NODE_ENV !== 'production';
const app = next({ dev });
const handle = app.getRequestHandler();

app.prepare().then(() => {
  createServer((req, res) => {
    // Node reports IPv4 clients on a dual-stack socket as ::ffff:a.b.c.d —
    // strip that prefix so the log shows a plain, familiar IPv4 address.
    const ip = (req.socket.remoteAddress || '').replace(/^::ffff:/, '');
    req.headers['x-forwarded-for'] = ip;
    handle(req, res);
  }).listen(port, () => {
    console.log(`> Ready on http://localhost:${port} (${dev ? 'development' : process.env.NODE_ENV})`);
  });
});
