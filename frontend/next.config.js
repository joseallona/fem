/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  webpack: (config) => {
    const path = require("path");
    const d3Path = path.resolve(__dirname, "node_modules/d3/dist/d3.js");
    config.resolve.alias["d3"] = d3Path;
    config.module.rules.push({
      test: d3Path,
      type: "javascript/auto",
    });
    return config;
  },
};

module.exports = nextConfig;
