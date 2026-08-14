import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  devIndicators: false,
  turbopack: {
    // Restrict Turbopack's workspace root to this directory only.
    // Without this, Turbopack walks up to H:\opr-mis1 (where the Playwright
    // package-lock.json lives) and scans the entire Python backend folder,
    // causing 60-second compiles and Rust OOM crashes.
    // Must be absolute — Turbopack rejects relative paths.
    root: __dirname,
  },
  allowedDevOrigins: ['10.135.5.15', '192.168.1.7', 'localhost', '127.0.0.1'],
  experimental: {
    // Default proxy body buffer is 10MB (silently truncated past that, no
    // error) — DSP monthly PDFs run up to ~19MB, so raise the ceiling well
    // above that.
    proxyClientMaxBodySize: '30mb',
    // Next dev's rewrite proxy hardcodes a 30s timeout by default
    // (server/lib/router-utils/proxy-request.js) — too short for
    // /api/admin/backups/*/restore, which shells out to mysqldump (pre-restore
    // snapshot) then mysql (the actual restore), each with its own 180s
    // subprocess timeout on the backend. A 10MB dump alone took ~40s in
    // testing, well past 30s, causing the proxy to abort with ECONNRESET and
    // return its own plain-text "Internal Server Error" before the backend's
    // real (JSON) response ever arrived. Set comfortably above the backend's
    // worst case (180s + 180s) so the backend's own timeout handling always
    // wins.
    proxyTimeout: 400000,
  },
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://127.0.0.1:8082/api/:path*',
      },
    ];
  },
};
export default nextConfig;