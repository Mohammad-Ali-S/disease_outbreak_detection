import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    output: 'export',
    trailingSlash: true,
    // Disable image optimization as it requires a server
    images: {
        unoptimized: true,
    },
};

export default nextConfig;
