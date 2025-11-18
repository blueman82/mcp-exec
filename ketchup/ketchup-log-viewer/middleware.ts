/**
 * Security Middleware
 *
 * This middleware provides security features including:
 * - Rate limiting for API endpoints
 * - Input validation and sanitization
 * - Additional security headers
 * - Request logging for security monitoring
 */

import { NextRequest, NextResponse } from 'next/server';
import { headers } from 'next/headers';

// Rate limiting configuration
const RATE_LIMITS = {
  // Global rate limit: 100 requests per minute per IP
  global: {
    windowMs: 60 * 1000, // 1 minute
    max: 100,
  },
  // API rate limit: 50 requests per minute per IP
  api: {
    windowMs: 60 * 1000, // 1 minute
    max: 50,
  },
  // Search rate limit: 20 requests per minute per IP
  search: {
    windowMs: 60 * 1000, // 1 minute
    max: 20,
  },
};

// In-memory rate limit store (in production, use Redis or similar)
const rateLimitStore = new Map<string, { count: number; resetTime: number }>();

// Clean up expired entries
function cleanupRateLimitStore() {
  const now = Date.now();
  for (const [key, data] of rateLimitStore.entries()) {
    if (now > data.resetTime) {
      rateLimitStore.delete(key);
    }
  }
}

// Check if a request is rate limited
function isRateLimited(identifier: string, limit: { windowMs: number; max: number }): boolean {
  const now = Date.now();
  const existing = rateLimitStore.get(identifier);

  if (!existing || now > existing.resetTime) {
    // Reset or create new entry
    rateLimitStore.set(identifier, {
      count: 1,
      resetTime: now + limit.windowMs,
    });
    return false;
  }

  // Increment count
  existing.count++;

  // Check if limit exceeded
  if (existing.count > limit.max) {
    return true;
  }

  return false;
}

// Generate rate limit identifier
function getRateLimitIdentifier(request: NextRequest): string {
  // Try to get real IP from various headers
  const forwarded = request.headers.get('x-forwarded-for');
  const realIp = request.headers.get('x-real-ip');

  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  if (realIp) {
    return realIp;
  }

  // Fallback to user agent hash (less reliable but better than nothing)
  const userAgent = request.headers.get('user-agent') || '';
  return Buffer.from(userAgent).toString('base64');
}

// Input validation functions
function validateInput(input: string, maxLength: number = 1000): boolean {
  if (!input || typeof input !== 'string') {
    return false;
  }

  if (input.length > maxLength) {
    return false;
  }

  // Check for dangerous patterns
  const dangerousPatterns = [
    /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi,
    /javascript:/gi,
    /on\w+\s*=/gi,
    /<iframe\b[^>]*>/gi,
    /<object\b[^>]*>/gi,
    /<embed\b[^>]*>/gi,
    /vbscript:/gi,
    /data:text\/html/gi,
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(input)) {
      return false;
    }
  }

  return true;
}

// Sanitize input for safe display
function sanitizeInput(input: string): string {
  if (!input || typeof input !== 'string') {
    return '';
  }

  return input
    // Remove HTML tags
    .replace(/<[^>]*>/g, '')
    // Remove potentially dangerous characters
    .replace(/[<>\"'&]/g, '')
    // Limit length
    .substring(0, 1000)
    .trim();
}

// Security headers
const SECURITY_HEADERS = {
  'X-Content-Type-Options': 'nosniff',
  'X-Frame-Options': 'DENY',
  'X-XSS-Protection': '1; mode=block',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=(), payment=()',
  'Strict-Transport-Security': 'max-age=31536000; includeSubDomains; preload',
};

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const identifier = getRateLimitIdentifier(request);

  // Clean up expired entries periodically
  if (Math.random() < 0.01) { // 1% chance to clean up
    cleanupRateLimitStore();
  }

  // Apply global rate limiting
  if (isRateLimited(identifier, RATE_LIMITS.global)) {
    return new NextResponse('Too Many Requests', {
      status: 429,
      headers: {
        'Retry-After': '60',
        'Content-Type': 'text/plain',
        ...SECURITY_HEADERS,
      },
    });
  }

  // Apply stricter rate limiting to API routes
  if (pathname.startsWith('/api/')) {
    // API rate limit
    if (isRateLimited(`api:${identifier}`, RATE_LIMITS.api)) {
      return new NextResponse('Too Many Requests', {
        status: 429,
        headers: {
          'Retry-After': '60',
          'Content-Type': 'text/plain',
          ...SECURITY_HEADERS,
        },
      });
    }

    // Special rate limiting for search endpoints
    if (pathname.includes('/search') || pathname.includes('/logs/fetch')) {
      if (isRateLimited(`search:${identifier}`, RATE_LIMITS.search)) {
        return new NextResponse('Too Many Requests', {
          status: 429,
          headers: {
            'Retry-After': '60',
            'Content-Type': 'text/plain',
            ...SECURITY_HEADERS,
          },
        });
      }
    }

    // Validate API request body for POST/PUT requests
    // NOTE: Cannot read request body in middleware as it will be consumed
    // and unavailable to route handlers. Only validate headers here.
    if (['POST', 'PUT', 'PATCH'].includes(request.method)) {
      // Validate Content-Length header for size (max 1MB)
      const contentLength = request.headers.get('content-length');
      if (contentLength && parseInt(contentLength) > 1024 * 1024) {
        return new NextResponse('Request Entity Too Large', {
          status: 413,
          headers: SECURITY_HEADERS,
        });
      }

      // Validate Content-Type header
      const contentType = request.headers.get('content-type');
      if (contentType && !contentType.includes('application/json') && !contentType.includes('multipart/form-data')) {
        return new NextResponse('Unsupported Media Type', {
          status: 415,
          headers: SECURITY_HEADERS,
        });
      }

      // Body validation must be done in individual route handlers
      // to avoid consuming the request stream
    }
  }

  // Create response with security headers
  const response = NextResponse.next();

  // Apply security headers
  Object.entries(SECURITY_HEADERS).forEach(([key, value]) => {
    response.headers.set(key, value);
  });

  // Add rate limit headers
  const limitData = rateLimitStore.get(identifier);
  if (limitData) {
    response.headers.set('X-RateLimit-Limit', RATE_LIMITS.global.max.toString());
    response.headers.set('X-RateLimit-Remaining', Math.max(0, RATE_LIMITS.global.max - limitData.count).toString());
    response.headers.set('X-RateLimit-Reset', new Date(limitData.resetTime).toUTCString());
  }

  // Add security nonce for CSP if needed
  const nonce = Buffer.from(crypto.getRandomValues(new Uint8Array(16))).toString('base64');
  response.headers.set('X-Content-Security-Policy-Nonce', nonce);

  return response;
}

// Configure which routes the middleware should run on
export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public (public files)
     */
    '/((?!_next/static|_next/image|favicon.ico|public).*)',
  ],
};