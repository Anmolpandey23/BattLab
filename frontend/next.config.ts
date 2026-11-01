import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // @ts-expect-error Next.js 16 agentRules flag to disable AGENTS.md auto-generation
  agentRules: false,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
