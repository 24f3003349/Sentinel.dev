import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Keeps tracing confined to this app when a parent workspace has lockfiles.
  outputFileTracingRoot: __dirname,
};

export default nextConfig;
