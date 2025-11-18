/**
 * Next.js Configuration
 *
 * This file configures the Next.js application with security headers,
 * including Content Security Policy (CSP) for XSS prevention.
 */

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Security headers configuration
  async headers() {
    return [
      {
        // Apply these headers to all routes
        source: '/(.*)',
        headers: [
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'camera=(), microphone=(), geolocation=()',
          },
        ],
      },
      {
        // Apply Content Security Policy to HTML pages
        source: '/_next/static/(.*)',
        headers: [
          {
            key: 'Cache-Control',
            value: 'public, max-age=31536000, immutable',
          },
        ],
      },
      {
        // API routes get different CSP (more restrictive)
        source: '/api/(.*)',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline'",
              "img-src 'self' data: blob:",
              "font-src 'self' data:",
              "connect-src 'self' ws: wss:",
              "object-src 'none'",
              "base-uri 'self'",
              "form-action 'self'",
              "frame-ancestors 'none'",
              "upgrade-insecure-requests",
            ].join('; '),
          },
        ],
      },
      {
        // Main application routes
        source: '/((?!api|_next/static|_next/image|favicon.ico).*)',
        headers: [
          {
            key: 'Content-Security-Policy',
            value: [
              // Default to self
              "default-src 'self'",

              // Allow inline scripts for React hydration
              "script-src 'self' 'unsafe-eval' 'unsafe-inline'",

              // Allow inline styles for Tailwind CSS
              "style-src 'self' 'unsafe-inline'",

              // Allow images from our domain and data URLs
              "img-src 'self' data: blob: https:",

              // Allow fonts from our domain and data URLs
              "font-src 'self' data:",

              // Allow connections to our API and WebSocket connections
              "connect-src 'self' ws: wss: https:",

              // Media restrictions
              "media-src 'self' blob:",

              // Prevent object and embed tags
              "object-src 'none'",
              "child-src 'none'",

              // Prevent base tag hijacking
              "base-uri 'self'",

              // Form actions only to same origin
              "form-action 'self'",

              // Prevent clickjacking
              "frame-ancestors 'none'",

              // Force HTTPS in production
              "upgrade-insecure-requests",

              // Allow prefetch and preload
              "prefetch-src 'self'",
              "preload-src 'self'",

              // Allow worker scripts for background processing
              "worker-src 'self' blob:",

              // Allow manifest for PWA
              "manifest-src 'self'",
            ].join('; '),
          },
        ],
      },
    ];
  },

  // React strict mode for development warnings
  reactStrictMode: process.env.NODE_ENV === 'development',

  // Experimental features
  experimental: {
    // Optimize package imports
    optimizePackageImports: ['lucide-react', '@tanstack/react-virtual'],
  },

  // Webpack configuration
  webpack: (config, { isServer }) => {
    // Add security plugins for client-side builds
    if (!isServer) {
      // Ensure proper handling of source maps in production
      config.devtool = process.env.NODE_ENV === 'production' ? 'hidden-source-map' : 'eval-source-map';
    }

    return config;
  },

  // Environment variables that should be available to the browser
  publicRuntimeConfig: {
    // Add any public config here
  },

  // Logging configuration
  logging: {
    fetches: {
      fullUrl: process.env.NODE_ENV === 'development',
    },
  },

  // Image optimization
  images: {
    domains: [], // Add any external image domains here
    formats: ['image/webp', 'image/avif'],
  },

  // Output configuration
  output: 'standalone',
};

module.exports = nextConfig;