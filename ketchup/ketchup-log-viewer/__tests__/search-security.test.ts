/**
 * Security Tests for Enhanced Search Functionality
 *
 * SECURITY: These tests verify that search-related security vulnerabilities
 * are properly blocked, including XSS attacks and ReDoS attacks.
 *
 * Phase 7: Security and Validation Implementation
 */

import { InputValidator } from '@/lib/input-validator';
import {
  sanitizeSearchResultText,
  sanitizeSearchMatch,
  sanitizeSearchResult,
  sanitizeSearchResults,
  sanitizeHighlightAttributes,
  createSafeSearchPreview,
  validateSearchIndex,
  sanitizeSearchStats,
} from '@/lib/security/search-sanitizer';
import type { SearchResult, SearchMatch } from '@/types/search';
import type { LogLine } from '@/types';

describe('InputValidator - Search Security Tests', () => {
  describe('validateSearchTerm', () => {
    describe('VALID inputs (should accept)', () => {
      it('accepts normal search terms', () => {
        expect(InputValidator.validateSearchTerm('error').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('connection timeout').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('Failed to load').valid).toBe(true);
      });

      it('accepts empty strings (clear search)', () => {
        expect(InputValidator.validateSearchTerm('').valid).toBe(true);
      });

      it('accepts search terms with special characters', () => {
        expect(InputValidator.validateSearchTerm('status: 404').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('user@example.com').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('path/to/file').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('price: $99.99').valid).toBe(true);
      });

      it('accepts search terms with unicode', () => {
        expect(InputValidator.validateSearchTerm('café').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('日本語').valid).toBe(true);
        expect(InputValidator.validateSearchTerm('emoji 🔍').valid).toBe(true);
      });

      it('accepts search terms up to 1000 characters', () => {
        const maxLength = 'a'.repeat(1000);
        expect(InputValidator.validateSearchTerm(maxLength).valid).toBe(true);
      });
    });

    describe('CRITICAL: XSS Attack Prevention (must reject)', () => {
      it('rejects script tags', () => {
        const result = InputValidator.validateSearchTerm('<script>alert("xss")</script>');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('script tag');
      });

      it('rejects script tags with variations', () => {
        expect(InputValidator.validateSearchTerm('<SCRIPT>alert("xss")</SCRIPT>').valid).toBe(
          false
        );
        expect(InputValidator.validateSearchTerm('<script src="evil.js"></script>').valid).toBe(
          false
        );
        expect(
          InputValidator.validateSearchTerm('<script type="text/javascript">alert(1)</script>')
            .valid
        ).toBe(false);
      });

      it('rejects javascript: protocol', () => {
        const result = InputValidator.validateSearchTerm('javascript:alert("xss")');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('javascript protocol');
      });

      it('rejects event handlers', () => {
        const result = InputValidator.validateSearchTerm('onclick="alert(1)"');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('event handler');
      });

      it('rejects various event handlers', () => {
        expect(InputValidator.validateSearchTerm('onerror="alert(1)"').valid).toBe(false);
        expect(InputValidator.validateSearchTerm('onload="malicious()"').valid).toBe(false);
        expect(InputValidator.validateSearchTerm('onmouseover="steal()"').valid).toBe(false);
      });

      it('rejects iframe tags', () => {
        const result = InputValidator.validateSearchTerm('<iframe src="evil.com"></iframe>');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('iframe tag');
      });

      it('rejects object tags', () => {
        const result = InputValidator.validateSearchTerm('<object data="evil.swf"></object>');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('object tag');
      });

      it('rejects embed tags', () => {
        const result = InputValidator.validateSearchTerm('<embed src="evil.swf">');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('embed tag');
      });

      it('rejects vbscript: protocol', () => {
        const result = InputValidator.validateSearchTerm('vbscript:msgbox("xss")');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('vbscript protocol');
      });

      it('rejects data URI HTML', () => {
        const result = InputValidator.validateSearchTerm(
          'data:text/html,<script>alert(1)</script>'
        );
        expect(result.valid).toBe(false);
        // Note: script tag is detected first, which is also a valid rejection
        expect(result.error).toMatch(/script tag|data URI HTML/);
      });
    });

    describe('Edge cases', () => {
      it('rejects non-string inputs', () => {
        expect(InputValidator.validateSearchTerm(null as any).valid).toBe(false);
        expect(InputValidator.validateSearchTerm(undefined as any).valid).toBe(false);
        expect(InputValidator.validateSearchTerm(123 as any).valid).toBe(false);
        expect(InputValidator.validateSearchTerm({} as any).valid).toBe(false);
      });

      it('rejects search terms over 1000 characters', () => {
        const tooLong = 'a'.repeat(1001);
        const result = InputValidator.validateSearchTerm(tooLong);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('too long');
      });

      it('rejects control characters', () => {
        const result = InputValidator.validateSearchTerm('test\x00null');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('control characters');
      });

      it('rejects various control characters', () => {
        expect(InputValidator.validateSearchTerm('test\x01').valid).toBe(false);
        expect(InputValidator.validateSearchTerm('test\x1F').valid).toBe(false);
        expect(InputValidator.validateSearchTerm('test\x7F').valid).toBe(false);
      });
    });
  });

  describe('validateRegexPattern', () => {
    describe('VALID inputs (should accept)', () => {
      it('accepts simple regex patterns', () => {
        expect(InputValidator.validateRegexPattern('[0-9]+').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('error|warning').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('^test$').valid).toBe(true);
      });

      it('accepts patterns with common modifiers', () => {
        expect(InputValidator.validateRegexPattern('test*').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('test+').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('test?').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('test{1,3}').valid).toBe(true);
      });

      it('accepts patterns with character classes', () => {
        expect(InputValidator.validateRegexPattern('[a-z]+').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('[A-Z0-9]').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('\\d+').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('\\w+').valid).toBe(true);
      });

      it('accepts patterns with capture groups (up to 20)', () => {
        expect(InputValidator.validateRegexPattern('(error)|(warning)').valid).toBe(true);
        expect(InputValidator.validateRegexPattern('(\\d{3})-(\\d{4})').valid).toBe(true);
      });
    });

    describe('CRITICAL: ReDoS Attack Prevention (must reject)', () => {
      it('rejects catastrophic backtracking patterns (a+)+', () => {
        const result = InputValidator.validateRegexPattern('(a+)+');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('dangerous backtracking');
      });

      it('rejects catastrophic backtracking patterns (a*)*', () => {
        const result = InputValidator.validateRegexPattern('(a*)*');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('dangerous backtracking');
      });

      it('rejects catastrophic backtracking patterns (a+){n,m}', () => {
        const result = InputValidator.validateRegexPattern('(a+){2,5}');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('dangerous backtracking');
      });

      it('rejects catastrophic backtracking patterns (a|b)+', () => {
        const result = InputValidator.validateRegexPattern('(a|b)+c');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('dangerous backtracking');
      });

      it('rejects catastrophic backtracking patterns (a|b)*', () => {
        const result = InputValidator.validateRegexPattern('(a|b)*c');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('dangerous backtracking');
      });

      it('rejects nested quantifiers', () => {
        expect(InputValidator.validateRegexPattern('a*+').valid).toBe(false);
        expect(InputValidator.validateRegexPattern('a+*').valid).toBe(false);
        expect(InputValidator.validateRegexPattern('a**').valid).toBe(false);
        expect(InputValidator.validateRegexPattern('a++').valid).toBe(false);
      });

      it('rejects overly complex patterns', () => {
        // Pattern with high complexity score but under group limit
        // Score = length + (groups * 5) + (quantifiers * 3)
        // For 'a+'.repeat(201): length=402, groups=0, quantifiers=201
        // Complexity = 402 + 0 + (201 * 3) = 402 + 603 = 1005 > 1000
        const complexPattern = 'a+'.repeat(201); // No groups, high quantifier count
        const result = InputValidator.validateRegexPattern(complexPattern);
        expect(result.valid).toBe(false);
        expect(result.error).toMatch(/too complex|Too many capture groups/);
      });

      it('rejects patterns with too many capture groups', () => {
        const tooManyGroups = '(a)'.repeat(21);
        const result = InputValidator.validateRegexPattern(tooManyGroups);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Too many capture groups');
      });
    });

    describe('Edge cases', () => {
      it('rejects empty or null patterns', () => {
        expect(InputValidator.validateRegexPattern('').valid).toBe(false);
        expect(InputValidator.validateRegexPattern(null as any).valid).toBe(false);
        expect(InputValidator.validateRegexPattern(undefined as any).valid).toBe(false);
      });

      it('rejects patterns over 500 characters', () => {
        const tooLong = 'a'.repeat(501);
        const result = InputValidator.validateRegexPattern(tooLong);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('too long');
      });

      it('rejects invalid regex syntax', () => {
        const result = InputValidator.validateRegexPattern('[');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid regex pattern');
      });

      it('rejects more invalid regex patterns', () => {
        expect(InputValidator.validateRegexPattern('(unclosed').valid).toBe(false);
        expect(InputValidator.validateRegexPattern('[unclosed').valid).toBe(false);
        expect(InputValidator.validateRegexPattern('(?P<name)').valid).toBe(false);
      });
    });
  });
});

describe('Search Result Sanitization Tests', () => {
  describe('sanitizeSearchResultText', () => {
    it('sanitizes HTML tags', () => {
      expect(sanitizeSearchResultText('<div>test</div>')).not.toContain('<div>');
      expect(sanitizeSearchResultText('<script>alert(1)</script>')).not.toContain('<script>');
    });

    it('sanitizes HTML entities', () => {
      const result = sanitizeSearchResultText('test & test');
      expect(result).toContain('&amp;');
    });

    it('handles empty and null inputs', () => {
      expect(sanitizeSearchResultText('')).toBe('');
      expect(sanitizeSearchResultText(null as any)).toBe('');
      expect(sanitizeSearchResultText(undefined as any)).toBe('');
    });

    it('preserves normal text', () => {
      expect(sanitizeSearchResultText('normal text')).toBe('normal text');
      expect(sanitizeSearchResultText('error: connection failed')).toContain('error');
    });
  });

  describe('sanitizeSearchMatch', () => {
    it('clamps indices to valid ranges', () => {
      const logLine: LogLine = {
        content: 'test content',
        timestamp: '2025-10-15T10:00:00Z',
        server: 'prod1',
        container: 'ketchup-app',
        level: 'info',
      };

      const match: SearchMatch = {
        lineIndex: 0,
        log: logLine,
        matchStart: -10,
        matchEnd: 1000,
        score: 0.5,
        context: 'test context',
      };

      const sanitized = sanitizeSearchMatch(match, 100);

      expect(sanitized.matchStart).toBe(0);
      expect(sanitized.matchEnd).toBe(100);
    });

    it('does not modify valid indices', () => {
      const logLine: LogLine = {
        content: 'test content',
        timestamp: '2025-10-15T10:00:00Z',
        server: 'prod1',
        container: 'ketchup-app',
        level: 'info',
      };

      const match: SearchMatch = {
        lineIndex: 0,
        log: logLine,
        matchStart: 5,
        matchEnd: 10,
        score: 0.5,
        context: 'test context',
      };

      const sanitized = sanitizeSearchMatch(match, 100);

      expect(sanitized.matchStart).toBe(5);
      expect(sanitized.matchEnd).toBe(10);
    });
  });

  describe('sanitizeSearchResult', () => {
    it('sanitizes complete search result', () => {
      const logLine: LogLine = {
        content: '<script>alert(1)</script>',
        timestamp: '2025-10-15T10:00:00Z',
        server: 'prod1',
        container: 'ketchup-app',
        level: 'error',
      };

      const match: SearchMatch = {
        lineIndex: 0,
        log: logLine,
        matchStart: 0,
        matchEnd: 10,
        score: 0.9,
        context: '<script> context',
      };

      const result: SearchResult = {
        query: '<script>alert("test")</script>',
        matches: [match],
        totalMatches: 1,
        hasMore: false,
        isPartial: false,
        executionTime: 10,
        searchMode: 'text',
        filters: {},
        pages: [],
        pagination: {
          currentPage: 0,
          pageSize: 100,
          totalPages: 1,
        },
        progress: {
          completion: 100,
          chunksProcessed: 1,
          totalChunks: 1,
          estimatedRemainingMs: 0,
        },
      };

      const sanitized = sanitizeSearchResult(result);

      expect(sanitized.query).not.toContain('<script>');
      expect(sanitized.matches[0].log.content).not.toContain('<script>');
      expect(sanitized.matches[0].context).not.toContain('<script>');
    });
  });

  describe('sanitizeSearchResults', () => {
    it('limits number of results', () => {
      const mockResult: SearchResult = {
        query: 'test',
        matches: [],
        totalMatches: 0,
        hasMore: false,
        isPartial: false,
        executionTime: 10,
        searchMode: 'text',
        filters: {},
        pages: [],
        pagination: {
          currentPage: 0,
          pageSize: 100,
          totalPages: 0,
        },
        progress: {
          completion: 100,
          chunksProcessed: 1,
          totalChunks: 1,
          estimatedRemainingMs: 0,
        },
      };

      const results: SearchResult[] = Array(20000).fill(mockResult);

      const sanitized = sanitizeSearchResults(results, 100);

      expect(sanitized.length).toBe(100);
    });

    it('handles non-array inputs', () => {
      expect(sanitizeSearchResults(null as any)).toEqual([]);
      expect(sanitizeSearchResults(undefined as any)).toEqual([]);
      expect(sanitizeSearchResults('invalid' as any)).toEqual([]);
    });
  });

  describe('sanitizeHighlightAttributes', () => {
    it('only allows whitelisted classes', () => {
      const result = sanitizeHighlightAttributes('search-highlight malicious-class');

      expect(result.className).toContain('search-highlight');
      expect(result.className).not.toContain('malicious-class');
    });

    it('sanitizes data attributes', () => {
      const result = sanitizeHighlightAttributes('search-highlight', {
        'data-index': '5',
        'data-evil': '<script>alert(1)</script>',
        'evil-attr': 'should be filtered',
      });

      expect(result['data-index']).toBe('5');
      expect(result['data-evil']).not.toContain('<script>');
      expect(result['evil-attr']).toBeUndefined();
    });

    it('falls back to default class if none provided', () => {
      const result = sanitizeHighlightAttributes('');

      expect(result.className).toBe('search-highlight');
    });
  });

  describe('createSafeSearchPreview', () => {
    it('truncates long content', () => {
      const longText = 'a'.repeat(500);
      const preview = createSafeSearchPreview(longText, 100);

      expect(preview.length).toBeLessThanOrEqual(104); // 100 + '...'
    });

    it('sanitizes content', () => {
      const preview = createSafeSearchPreview('<script>alert(1)</script>');

      expect(preview).not.toContain('<script>');
    });

    it('handles empty input', () => {
      expect(createSafeSearchPreview('')).toBe('');
      expect(createSafeSearchPreview(null as any)).toBe('');
    });
  });

  describe('validateSearchIndex', () => {
    it('clamps index to valid range', () => {
      expect(validateSearchIndex(-5, 10)).toBe(0);
      expect(validateSearchIndex(100, 10)).toBe(9);
      expect(validateSearchIndex(5, 10)).toBe(5);
    });

    it('handles invalid inputs', () => {
      expect(validateSearchIndex(NaN, 10)).toBe(0);
      expect(validateSearchIndex('invalid' as any, 10)).toBe(0);
    });
  });

  describe('sanitizeSearchStats', () => {
    it('ensures numeric values are valid', () => {
      const stats = {
        totalResults: 100,
        matchCount: 50,
        invalidValue: NaN,
        negativeValue: -10,
      };

      const sanitized = sanitizeSearchStats(stats);

      expect(sanitized.totalResults).toBe(100);
      expect(sanitized.matchCount).toBe(50);
      expect(sanitized.invalidValue).toBe(0);
      expect(sanitized.negativeValue).toBe(0);
    });

    it('clamps values to safe range', () => {
      const stats = {
        veryLarge: Number.MAX_SAFE_INTEGER + 1000,
      };

      const sanitized = sanitizeSearchStats(stats);

      expect(sanitized.veryLarge).toBe(Number.MAX_SAFE_INTEGER);
    });
  });
});

/**
 * SECURITY ATTACK SCENARIOS BLOCKED BY THESE VALIDATIONS
 *
 * 1. CRITICAL: Search Term XSS Injection
 *    Before: User searches for: <script>document.cookie</script>
 *    Risk: Script executes in search results display
 *    After: ❌ Rejected - script tag detected
 *
 * 2. CRITICAL: Event Handler XSS
 *    Before: User searches for: onclick="alert('xss')"
 *    Risk: Event handler executes on click
 *    After: ❌ Rejected - event handler detected
 *
 * 3. CRITICAL: ReDoS Attack via Regex
 *    Before: User uses regex: (a+)+
 *    Risk: Browser hangs processing malicious regex
 *    After: ❌ Rejected - catastrophic backtracking detected
 *
 * 4. Resource Exhaustion
 *    Before: User searches with 10000 character term
 *    Risk: Server/client memory exhaustion
 *    After: ❌ Rejected - length limit exceeded
 *
 * 5. Stored XSS via Search Results
 *    Before: Log contains: <img src=x onerror="alert(1)">
 *    Risk: XSS executes when displaying search results
 *    After: ✅ Sanitized - HTML entities encoded
 */
