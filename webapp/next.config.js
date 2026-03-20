/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_OUTPUT === 'export' ? 'export' : undefined,
  images: {
    unoptimized: process.env.NEXT_OUTPUT === 'export',
  },
}

module.exports = nextConfig
