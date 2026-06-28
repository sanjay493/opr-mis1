import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));

/** @type {import('next').NextConfig} */
const nextConfig = {
  turbopack: {
    // Restrict Turbopack's workspace root to this directory only.
    // Without this, Turbopack walks up to H:\opr-mis1 (where the Playwright
    // package-lock.json lives) and scans the entire Python backend folder,
    // causing 60-second compiles and Rust OOM crashes.
    // Must be absolute — Turbopack rejects relative paths.
    root: __dirname,
  },
  allowedDevOrigins: ['192.168.1.7', 'localhost', '127.0.0.1'],
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