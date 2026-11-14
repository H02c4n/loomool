/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: "/media/:path*",
        destination: "http://minio:9000/loomool-media/:path*",
      },
    ];
  },
};

export default nextConfig;
