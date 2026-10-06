/** @type {import('next').NextConfig} */
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  experimental: {
    // LLM Q&A can exceed the default 30s proxy timeout, so relax it to 3 minutes
    proxyTimeout: 180000,
  },
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${BACKEND_URL}/api/:path*` },
      { source: "/healthz", destination: `${BACKEND_URL}/healthz` },
      { source: "/metrics", destination: `${BACKEND_URL}/metrics` },
    ];
  },
};

export default nextConfig;
