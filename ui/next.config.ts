import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // A janela do pywebview serve a pasta `out/` por HTTP local.
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
