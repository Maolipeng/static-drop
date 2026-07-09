import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  // In production, nginx proxies /api/* to FastAPI, so same-origin.
  // In dev, we proxy to the local FastAPI server.
  async rewrites() {
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/api/:path*",
          destination: `${process.env.API_URL || "http://localhost:8000"}/api/:path*`,
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
