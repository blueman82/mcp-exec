/**
 * Input Validator - Security Layer for User Inputs
 *
 * SECURITY: Prevents command injection attacks by validating all user-controlled
 * parameters before they are used in shell commands.
 *
 * Created: 2025-10-06
 * Purpose: Fix CRITICAL RCE vulnerabilities in log streaming API
 */

export interface ValidationResult {
  valid: boolean;
  error?: string;
}

export interface TailValidationResult extends ValidationResult {
  value?: number;
}

export interface SinceValidationResult extends ValidationResult {
  value?: string;
}

export class InputValidator {
  /**
   * Validate Docker container name
   *
   * Docker naming rules:
   * - Must start with alphanumeric character
   * - Can contain: a-z, A-Z, 0-9, dash (-), underscore (_), period (.)
   * - Length: 1-255 characters
   * - MUST NOT contain shell metacharacters
   *
   * @param name - Container name from user input
   * @returns Validation result with error message if invalid
   */
  static validateContainerName(name: string): ValidationResult {
    // Check for null/undefined/empty
    if (!name || typeof name !== 'string') {
      return { valid: false, error: 'Container name is required' };
    }

    // Check length constraints
    if (name.length > 255) {
      return { valid: false, error: 'Container name too long (max 255 characters)' };
    }

    if (name.length === 0) {
      return { valid: false, error: 'Container name cannot be empty' };
    }

    // Docker naming rules: [a-zA-Z0-9][a-zA-Z0-9_.-]*
    // Must start with alphanumeric, then can contain alphanumeric, underscore, dash, period
    const validPattern = /^[a-zA-Z0-9][a-zA-Z0-9_.-]*$/;
    if (!validPattern.test(name)) {
      return {
        valid: false,
        error: 'Invalid container name format. Must start with alphanumeric and contain only [a-zA-Z0-9_.-]'
      };
    }

    // CRITICAL: Block shell metacharacters to prevent command injection
    // These characters allow attackers to chain commands, substitute commands, or redirect I/O
    const dangerousChars = /[;&|`$(){}[\]<>'"\\!]/;
    if (dangerousChars.test(name)) {
      return {
        valid: false,
        error: 'Container name contains invalid characters. Shell metacharacters are not allowed.'
      };
    }

    // Additional check: Block newlines and null bytes
    if (name.includes('\n') || name.includes('\r') || name.includes('\0')) {
      return { valid: false, error: 'Container name contains invalid control characters' };
    }

    return { valid: true };
  }

  /**
   * Validate tail parameter (number of log lines)
   *
   * Requirements:
   * - Must be a positive integer
   * - Range: 1 to 10000 (prevent resource exhaustion)
   * - Must be numeric only (no shell metacharacters)
   *
   * @param tail - Tail parameter from user input
   * @returns Validation result with parsed value if valid
   */
  static validateTailParameter(tail: string): TailValidationResult {
    // Allow empty/null for default value
    if (!tail || typeof tail !== 'string') {
      return { valid: true, value: 1000 }; // Default
    }

    // CRITICAL: Must be numeric only - reject any non-digit characters
    // This prevents injection like: "1000; rm -rf /" or "1000$(whoami)"
    if (!/^\d+$/.test(tail)) {
      return {
        valid: false,
        error: 'Tail must be a positive integer (digits only)'
      };
    }

    // Parse to integer
    const num = parseInt(tail, 10);

    // Check range (prevent resource exhaustion and negative values)
    if (num < 1) {
      return { valid: false, error: 'Tail must be at least 1' };
    }

    if (num > 10000) {
      return {
        valid: false,
        error: 'Tail cannot exceed 10000 (resource limit)'
      };
    }

    return { valid: true, value: num };
  }

  /**
   * Validate server name
   *
   * Only allow whitelisted server names to prevent SSRF attacks
   *
   * @param server - Server name from user input
   * @returns Validation result
   */
  static validateServerName(server: string): ValidationResult {
    const validServers = ['prod1', 'prod2'];

    if (!server || typeof server !== 'string') {
      return { valid: false, error: 'Server name is required' };
    }

    if (!validServers.includes(server)) {
      return {
        valid: false,
        error: `Invalid server name. Must be one of: ${validServers.join(', ')}`
      };
    }

    return { valid: true };
  }

  /**
   * Validate since parameter for time filtering
   *
   * Docker since parameter format:
   * - Duration formats: 1h, 30m, 24h, 7d
   * - ISO timestamps: 2023-10-15T10:30:00Z
   * - Must prevent shell injection and format attacks
   *
   * @param since - Since parameter from user input
   * @returns Validation result with sanitized value if valid
   */
  static validateSinceParameter(since: string): SinceValidationResult {
    // Allow empty/null for default value
    if (!since || typeof since !== 'string') {
      return { valid: true, value: '24h' }; // Default to 24 hours
    }

    // Check length (prevent very long inputs)
    if (since.length > 50) {
      return {
        valid: false,
        error: 'Since parameter too long (max 50 characters)'
      };
    }

    // Check for duration format (number + unit)
    const durationPattern = /^\d+[smhdw]$/; // e.g., 1h, 30m, 24h, 7d, 1w
    if (durationPattern.test(since)) {
      return { valid: true, value: since };
    }

    // Check for ISO 8601 timestamp format (basic validation)
    const isoPattern = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}/; // Basic ISO format
    if (isoPattern.test(since)) {
      return { valid: true, value: since };
    }

    // CRITICAL: Block shell metacharacters to prevent command injection
    const dangerousChars = /[;&|`$(){}[\]<>'"\\!]/;
    if (dangerousChars.test(since)) {
      return {
        valid: false,
        error: 'Since parameter contains invalid characters'
      };
    }

    return {
      valid: false,
      error: 'Invalid since format. Use duration (1h, 30m, 24h) or ISO timestamp'
    };
  }

  /**
   * Validate search term for enhanced search functionality
   *
   * SECURITY: Prevents XSS attacks and ensures search terms are safe to process
   *
   * Requirements:
   * - Maximum length: 1000 characters
   * - No script tags or javascript: protocols
   * - No event handlers (onclick, onerror, etc.)
   * - No dangerous HTML tags
   *
   * @param term - Search term from user input
   * @returns Validation result with error message if invalid
   */
  static validateSearchTerm(term: string): ValidationResult {
    // Check for null/undefined/empty
    if (typeof term !== 'string') {
      return { valid: false, error: 'Search term must be a string' };
    }

    // Allow empty strings (clear search)
    if (term.length === 0) {
      return { valid: true };
    }

    // Length limits (prevent resource exhaustion)
    if (term.length > 1000) {
      return { valid: false, error: 'Search term too long (max 1000 characters)' };
    }

    // XSS prevention - block dangerous patterns
    const dangerousPatterns = [
      { pattern: /<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, name: 'script tag' },
      { pattern: /javascript:/gi, name: 'javascript protocol' },
      { pattern: /on\w+\s*=/gi, name: 'event handler' },
      { pattern: /<iframe\b[^>]*>/gi, name: 'iframe tag' },
      { pattern: /<object\b[^>]*>/gi, name: 'object tag' },
      { pattern: /<embed\b[^>]*>/gi, name: 'embed tag' },
      { pattern: /vbscript:/gi, name: 'vbscript protocol' },
      { pattern: /data:text\/html/gi, name: 'data URI HTML' },
    ];

    for (const { pattern, name } of dangerousPatterns) {
      if (pattern.test(term)) {
        return { valid: false, error: `Invalid characters in search term: ${name} detected` };
      }
    }

    // Block control characters (except common whitespace)
    if (/[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]/.test(term)) {
      return { valid: false, error: 'Search term contains invalid control characters' };
    }

    return { valid: true };
  }

  /**
   * Validate regex pattern for search functionality
   *
   * SECURITY: Prevents ReDoS (Regular Expression Denial of Service) attacks
   *
   * Requirements:
   * - Must be valid regex syntax
   * - Complexity limit to prevent ReDoS
   * - No catastrophic backtracking patterns
   * - Maximum capture groups limit
   *
   * @param pattern - Regex pattern from user input
   * @returns Validation result with error message if invalid
   */
  static validateRegexPattern(pattern: string): ValidationResult {
    // Check for null/undefined
    if (!pattern || typeof pattern !== 'string') {
      return { valid: false, error: 'Regex pattern is required' };
    }

    // Length check
    if (pattern.length > 500) {
      return { valid: false, error: 'Regex pattern too long (max 500 characters)' };
    }

    // Try to compile the regex
    try {
      new RegExp(pattern);
    } catch (e) {
      const error = e as Error;
      return { valid: false, error: `Invalid regex pattern: ${error.message}` };
    }

    // Calculate complexity score to prevent ReDoS
    // Score = length + (number of groups * 5) + (number of quantifiers * 3)
    const groupCount = (pattern.match(/\(/g) || []).length;
    const quantifierCount = (pattern.match(/[*+?{]/g) || []).length;
    const complexity = pattern.length + (groupCount * 5) + (quantifierCount * 3);

    if (complexity > 1000) {
      return { valid: false, error: 'Regex pattern too complex (prevents ReDoS attacks)' };
    }

    // Check for excessive capture groups (max 20)
    if (groupCount > 20) {
      return { valid: false, error: 'Too many capture groups (max 20)' };
    }

    // Detect catastrophic backtracking patterns
    // These patterns are known to cause exponential time complexity
    const catastrophicPatterns = [
      /\(.*\+.*\)\+/,           // (a+)+
      /\(.*\*.*\)\*/,           // (a*)*
      /\(.*\+.*\)\{/,           // (a+){n,m}
      /\(.*\|.*\)\+/,           // (a|b)+
      /\(.*\|.*\)\*/,           // (a|b)*
      /\(\?\:.*\+.*\)\+/,       // (?:a+)+
      /\(\?\=.*\+/,             // (?=a+)...
      /\(\?\!.*\+/,             // (?!a+)...
    ];

    for (const catPattern of catastrophicPatterns) {
      if (catPattern.test(pattern)) {
        return { valid: false, error: 'Regex pattern contains dangerous backtracking' };
      }
    }

    // Check for nested quantifiers (also dangerous)
    if (/\*\+|\+\*|\*\*|\+\+|\?\+|\*\?/.test(pattern)) {
      return { valid: false, error: 'Regex pattern contains nested quantifiers' };
    }

    return { valid: true };
  }

  /**
   * Sanitize string for safe shell usage (backup defense layer)
   *
   * WARNING: Prefer validation + rejection over sanitization.
   * This is a backup defense layer only.
   *
   * @param input - String to sanitize
   * @returns Sanitized string with dangerous characters removed
   */
  static sanitizeForShell(input: string): string {
    // Remove all non-alphanumeric except dash, underscore, period
    return input.replace(/[^a-zA-Z0-9_.-]/g, '');
  }
}
