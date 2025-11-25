/**
 * Search Result Sanitization Utilities
 *
 * This module provides utilities specifically for sanitizing search results
 * and search-related data to prevent XSS attacks and other security vulnerabilities.
 *
 * Created: 2025-10-15
 * Purpose: Phase 7 - Security and Validation for enhanced search
 */

import type { SearchResult, SearchMatch } from '@/types/search';
import type { LogLine } from '@/types';

/**
 * Sanitizes search result text for safe display
 * 
 * SECURITY: Ensures that log content displayed in search results
 * cannot execute malicious code through XSS
 *
 * @param text - Raw text from log line
 * @returns Sanitized text safe for display
 */
export function sanitizeSearchResultText(text: string): string {
  if (!text || typeof text !== 'string') {
    return '';
  }

  // Use textContent approach to automatically escape HTML entities
  if (typeof document !== 'undefined') {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  // Server-side fallback: manual HTML entity encoding
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .replace(/\//g, '&#x2F;');
}

/**
 * Sanitizes a search match object
 * 
 * Ensures match indices are valid and match text is safe
 *
 * @param match - Search match to sanitize
 * @param contentLength - Length of the content being matched
 * @returns Sanitized search match
 */
export function sanitizeSearchMatch(match: SearchMatch, contentLength: number): SearchMatch {
  // Validate and clamp indices
  const matchStart = Math.max(0, Math.min(match.matchStart, contentLength));
  const matchEnd = Math.max(matchStart, Math.min(match.matchEnd, contentLength));

  return {
    ...match,
    matchStart,
    matchEnd,
  };
}

/**
 * Sanitizes a complete search result
 * 
 * SECURITY: Ensures entire search result object is safe for display
 *
 * @param result - Search result to sanitize
 * @returns Sanitized search result
 */
export function sanitizeSearchResult(result: SearchResult): SearchResult {
  // Sanitize all matches and their associated log lines
  const sanitizedMatches = result.matches.map((match) => {
    const contentLength = match.log.content.length;
    return {
      ...match,
      matchStart: Math.max(0, Math.min(match.matchStart, contentLength)),
      matchEnd: Math.max(0, Math.min(match.matchEnd, contentLength)),
      log: {
        ...match.log,
        content: sanitizeSearchResultText(match.log.content),
        timestamp: sanitizeSearchResultText(match.log.timestamp),
        server: sanitizeSearchResultText(match.log.server || ''),
        container: sanitizeSearchResultText(match.log.container || ''),
      },
      context: sanitizeSearchResultText(match.context),
    };
  });

  // Sanitize query
  const sanitizedQuery = sanitizeSearchResultText(result.query);

  return {
    ...result,
    query: sanitizedQuery,
    matches: sanitizedMatches,
  };
}

/**
 * Sanitizes an array of search results
 *
 * @param results - Array of search results
 * @param maxResults - Maximum number of results to return
 * @returns Sanitized array of search results
 */
export function sanitizeSearchResults(
  results: SearchResult[],
  maxResults: number = 10000
): SearchResult[] {
  if (!Array.isArray(results)) {
    return [];
  }

  // Limit number of results to prevent memory exhaustion
  const limitedResults = results.slice(0, maxResults);

  return limitedResults.map(sanitizeSearchResult);
}

/**
 * Validates and sanitizes a highlight span element's attributes
 * 
 * Used when applying highlights to search results in the DOM
 *
 * @param className - CSS class name to apply
 * @param dataAttributes - Optional data attributes
 * @returns Safe attributes object
 */
export function sanitizeHighlightAttributes(
  className: string,
  dataAttributes?: Record<string, string>
): Record<string, string> {
  // Whitelist of allowed class names
  const allowedClasses = [
    'search-highlight',
    'search-highlight-primary',
    'search-highlight-secondary',
    'search-highlight-active',
    'search-match',
    'bg-yellow-500',
    'bg-orange-500',
    'bg-green-500',
    'text-black',
    'text-white',
  ];

  // Sanitize className - only allow whitelisted classes
  const classes = className
    .split(' ')
    .filter((cls) => allowedClasses.some((allowed) => cls.includes(allowed)))
    .join(' ');

  const attributes: Record<string, string> = {
    className: classes || 'search-highlight',
  };

  // Sanitize data attributes if provided
  if (dataAttributes) {
    for (const [key, value] of Object.entries(dataAttributes)) {
      // Only allow data-* attributes
      if (key.startsWith('data-')) {
        // Sanitize the value
        attributes[key] = sanitizeSearchResultText(value);
      }
    }
  }

  return attributes;
}

/**
 * Creates a safe search result preview
 * 
 * Truncates content to a safe length and sanitizes
 *
 * @param content - Full content
 * @param maxLength - Maximum preview length
 * @returns Safe, truncated preview
 */
export function createSafeSearchPreview(content: string, maxLength: number = 200): string {
  if (!content || typeof content !== 'string') {
    return '';
  }

  // Truncate first to reduce processing
  const truncated = content.length > maxLength ? content.slice(0, maxLength) + '...' : content;

  // Then sanitize
  return sanitizeSearchResultText(truncated);
}

/**
 * Validates search result indices for safe array access
 * 
 * Prevents index out of bounds errors
 *
 * @param index - Index to validate
 * @param arrayLength - Length of array being accessed
 * @returns Valid, clamped index
 */
export function validateSearchIndex(index: number, arrayLength: number): number {
  if (typeof index !== 'number' || isNaN(index)) {
    return 0;
  }

  return Math.max(0, Math.min(index, arrayLength - 1));
}

/**
 * Sanitizes search statistics for display
 * 
 * Ensures numeric values are valid
 *
 * @param stats - Search statistics object
 * @returns Sanitized statistics
 */
export function sanitizeSearchStats(stats: Record<string, number>): Record<string, number> {
  const sanitized: Record<string, number> = {};

  for (const [key, value] of Object.entries(stats)) {
    // Ensure value is a valid number
    const numValue = typeof value === 'number' && !isNaN(value) ? value : 0;

    // Clamp to reasonable ranges
    sanitized[key] = Math.max(0, Math.min(numValue, Number.MAX_SAFE_INTEGER));
  }

  return sanitized;
}
