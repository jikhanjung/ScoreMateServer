import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  webpack: (config) => {
    // Handle canvas module for react-pdf
    config.resolve.alias.canvas = false;
    
    // Handle worker files
    config.resolve.fallback = {
      ...config.resolve.fallback,
      canvas: false,
    };
    
    return config;
  },
  // Experimental features for better PDF support
  experimental: {
    esmExternals: 'loose',
  },
};

export default nextConfig;
