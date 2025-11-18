/**
 * Rate Limiting Utilities
 *
 * This module provides rate limiting functionality to prevent abuse
 * and ensure fair usage of API resources.
 */

interface RateLimitConfig {
  windowMs: number;
  max: number;
  message?: string;
}

interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetTime: number;
  retryAfter?: number;
}

/**
 * In-memory rate limiter implementation
 * In production, consider using Redis or another distributed store
 */
export class RateLimiter {
  private store: Map<string, { count: number; resetTime: number; windowMs: number }>;

  constructor() {
    this.store = new Map();

    // Clean up expired entries every minute
    setInterval(() => this.cleanup(), 60000);
  }

  /**
   * Check if a request is allowed
   * @param identifier - Unique identifier for the client
   * @param config - Rate limit configuration
   * @returns Rate limit result
   */
  public checkLimit(identifier: string, config: RateLimitConfig): RateLimitResult {
    const now = Date.now();
    const key = identifier;

    const existing = this.store.get(key);

    // Create new entry if none exists or if it's expired
    if (!existing || now > existing.resetTime) {
      this.store.set(key, {
        count: 1,
        resetTime: now + config.windowMs,
        windowMs: config.windowMs,
      });

      return {
        allowed: true,
        remaining: config.max - 1,
        resetTime: now + config.windowMs,
      };
    }

    // Check if limit exceeded
    if (existing.count >= config.max) {
      const retryAfter = Math.ceil((existing.resetTime - now) / 1000);

      return {
        allowed: false,
        remaining: 0,
        resetTime: existing.resetTime,
        retryAfter,
      };
    }

    // Increment count
    existing.count++;

    return {
      allowed: true,
      remaining: config.max - existing.count,
      resetTime: existing.resetTime,
    };
  }

  /**
   * Get current rate limit status
   * @param identifier - Unique identifier for the client
   * @returns Current rate limit status
   */
  public getStatus(identifier: string): {
    count: number;
    resetTime: number;
    windowMs: number;
  } | null {
    const now = Date.now();
    const existing = this.store.get(identifier);

    if (!existing || now > existing.resetTime) {
      return null;
    }

    return {
      count: existing.count,
      resetTime: existing.resetTime,
      windowMs: existing.windowMs,
    };
  }

  /**
   * Clean up expired entries
   */
  private cleanup(): void {
    const now = Date.now();
    for (const [key, data] of this.store.entries()) {
      if (now > data.resetTime) {
        this.store.delete(key);
      }
    }
  }

  /**
   * Reset rate limit for a specific identifier
   * @param identifier - Unique identifier for the client
   */
  public reset(identifier: string): void {
    this.store.delete(identifier);
  }

  /**
   * Clear all rate limits
   */
  public clear(): void {
    this.store.clear();
  }
}

// Global rate limiter instance
const globalRateLimiter = new RateLimiter();

// Predefined rate limit configurations
export const RATE_LIMITS = {
  GLOBAL: {
    windowMs: 60 * 1000, // 1 minute
    max: 100,
    message: 'Too many requests. Please try again later.',
  },
  SEARCH: {
    windowMs: 60 * 1000, // 1 minute
    max: 20,
    message: 'Too many search requests. Please wait before searching again.',
  },
  API: {
    windowMs: 60 * 1000, // 1 minute
    max: 50,
    message: 'API rate limit exceeded. Please try again later.',
  },
  AUTH: {
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 5,
    message: 'Too many authentication attempts. Please try again later.',
  },
  LOGS: {
    windowMs: 60 * 1000, // 1 minute
    max: 30,
    message: 'Too many log fetch requests. Please try again later.',
  },
} as const;

/**
 * Get client identifier from request
 * @param request - NextRequest object
 * @returns Client identifier
 */
export function getClientIdentifier(request: {
  ip?: string;
  headers: { get: (name: string) => string | null };
}): string {
  // Try to get real IP from various headers
  const forwarded = request.headers.get('x-forwarded-for');
  const realIp = request.headers.get('x-real-ip');
  const ip = request.ip;

  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  if (realIp) {
    return realIp;
  }
  if (ip) {
    return ip;
  }

  // Fallback to user agent hash (less reliable but better than nothing)
  const userAgent = request.headers.get('user-agent') || '';
  return Buffer.from(userAgent).toString('base64');
}

/**
 * Check rate limit using global instance
 * @param identifier - Client identifier
 * @param config - Rate limit configuration
 * @returns Rate limit result
 */
export function checkRateLimit(identifier: string, config: RateLimitConfig): RateLimitResult {
  return globalRateLimiter.checkLimit(identifier, config);
}

/**
 * Rate limiting middleware helper
 * @param request - NextRequest object
 * @param limitType - Type of rate limit to apply
 * @returns Rate limit check result
 */
export function checkRequestRateLimit(
  request: { ip?: string; headers: { get: (name: string) => string | null } },
  limitType: keyof typeof RATE_LIMITS
): RateLimitResult {
  const identifier = getClientIdentifier(request);
  const config = RATE_LIMITS[limitType];

  return checkRateLimit(identifier, config);
}

/**
 * Create rate limiter for specific use case
 * @param config - Rate limit configuration
 * @returns New rate limiter instance
 */
export function createRateLimiter(config: RateLimitConfig): RateLimiter {
  return new RateLimiter();
}

/**
 * Debounced function with rate limiting
 * @param fn - Function to debounce
 * @param delay - Debounce delay in milliseconds
 * @param rateLimit - Rate limit configuration
 * @returns Debounced and rate limited function
 */
export function createDebouncedRateLimitedFunction<T extends (...args: any[]) => any>(
  fn: T,
  delay: number,
  rateLimit: RateLimitConfig
): T {
  const limiter = new RateLimiter();
  let timeoutId: NodeJS.Timeout | null = null;

  return ((...args: Parameters<T>) => {
    const identifier = 'debounced-function';

    // Check rate limit
    const limitResult = limiter.checkLimit(identifier, rateLimit);
    if (!limitResult.allowed) {
      throw new Error(rateLimit.message || 'Rate limit exceeded');
    }

    // Clear existing timeout
    if (timeoutId) {
      clearTimeout(timeoutId);
    }

    // Set new timeout
    timeoutId = setTimeout(() => {
      fn(...args);
    }, delay);
  }) as T;
}

/**
 * Rate limited cache implementation
 */
export class RateLimitedCache<K, V> {
  private cache: Map<string, { value: V; timestamp: number; accessCount: number }>;
  private rateLimiter: RateLimiter;
  private maxSize: number;
  private ttl: number;

  constructor(maxSize: number = 100, ttl: number = 5 * 60 * 1000) {
    this.cache = new Map();
    this.rateLimiter = new RateLimiter();
    this.maxSize = maxSize;
    this.ttl = ttl;
  }

  /**
   * Get value from cache with rate limiting
   * @param key - Cache key
   * @param identifier - Client identifier
   * @returns Cached value or null
   */
  public get(key: K, identifier: string): V | null {
    // Check rate limit for cache access
    const limitResult = this.rateLimiter.checkLimit(
      `cache:${identifier}`,
      { windowMs: 1000, max: 100 } // 100 requests per second
    );

    if (!limitResult.allowed) {
      return null; // Silently fail on rate limit
    }

    const now = Date.now();
    const cached = this.cache.get(String(key));

    if (!cached || now - cached.timestamp > this.ttl) {
      this.cache.delete(String(key));
      return null;
    }

    // Update access count
    cached.accessCount++;
    return cached.value;
  }

  /**
   * Set value in cache
   * @param key - Cache key
   * @param value - Value to cache
   */
  public set(key: K, value: V): void {
    // Remove oldest entries if cache is full
    if (this.cache.size >= this.maxSize) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(String(key), {
      value,
      timestamp: Date.now(),
      accessCount: 1,
    });
  }

  /**
   * Clear cache
   */
  public clear(): void {
    this.cache.clear();
  }

  /**
   * Get cache statistics
   * @returns Cache statistics
   */
  public getStats(): {
    size: number;
    maxSize: number;
    hitRate: number;
    totalAccess: number;
  } {
    const totalAccess = Array.from(this.cache.values()).reduce(
      (sum, item) => sum + item.accessCount,
      0
    );

    return {
      size: this.cache.size,
      maxSize: this.maxSize,
      hitRate: totalAccess > 0 ? this.cache.size / totalAccess : 0,
      totalAccess,
    };
  }
}

/**
 * Adaptive rate limiter that adjusts based on system load
 */
export class AdaptiveRateLimiter extends RateLimiter {
  private loadThreshold: number;
  private currentLoad: number;

  constructor(loadThreshold: number = 0.8) {
    super();
    this.loadThreshold = loadThreshold;
    this.currentLoad = 0;
  }

  /**
   * Set current system load (0-1)
   * @param load - Current load value
   */
  public setLoad(load: number): void {
    this.currentLoad = Math.max(0, Math.min(1, load));
  }

  /**
   * Check rate limit with adaptive configuration
   * @param identifier - Client identifier
   * @param baseConfig - Base rate limit configuration
   * @returns Rate limit result
   */
  public checkAdaptiveLimit(identifier: string, baseConfig: RateLimitConfig): RateLimitResult {
    // Adjust limits based on load
    const loadFactor = 1 - this.currentLoad;
    const adjustedConfig = {
      ...baseConfig,
      max: Math.max(1, Math.floor(baseConfig.max * loadFactor)),
    };

    return super.checkLimit(identifier, adjustedConfig);
  }
}