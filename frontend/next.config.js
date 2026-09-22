/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Minimal, self-contained production build (.next/standalone) — the
  // Docker image copies just this output plus static assets, not the
  // full node_modules tree.
  output: 'standalone',
  webpack: (config) => {
    config.resolve.alias['@'] = require('path').resolve(__dirname, '.');
    return config;
  },
}

module.exports = nextConfig
