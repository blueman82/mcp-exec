/**
 * Input Sanitization and Security Utilities
 *
 * This module provides utilities for sanitizing user input to prevent
 * XSS attacks and other security vulnerabilities.
 */

/**
 * Sanitizes text input for safe display
 * @param input - Raw input string
 * @param maxLength - Maximum allowed length
 * @returns Sanitized string
 */
export function sanitizeText(input: string, maxLength: number = 1000): string {
  if (!input || typeof input !== 'string') {
    return '';
  }

  return input
    // Remove potentially dangerous HTML/JS patterns
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .replace(/<iframe\b[^>]*>/gi, '')
    .replace(/<object\b[^>]*>/gi, '')
    .replace(/<embed\b[^>]*>/gi, '')
    .replace(/vbscript:/gi, '')
    .replace(/data:text\/html/gi, '')
    // Remove HTML tags
    .replace(/<[^>]*>/g, '')
    // Remove dangerous characters
    .replace(/[<>\"'&]/g, '')
    // Limit length
    .substring(0, maxLength)
    .trim();
}

/**
 * Validates input against security patterns
 * @param input - Input to validate
 * @param maxLength - Maximum allowed length
 * @returns True if input is safe
 */
export function validateInput(input: string, maxLength: number = 1000): boolean {
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
    /eval\s*\(/gi,
    /setTimeout\s*\(/gi,
    /setInterval\s*\(/gi,
    /Function\s*\(/gi,
  ];

  for (const pattern of dangerousPatterns) {
    if (pattern.test(input)) {
      return false;
    }
  }

  return true;
}

/**
 * Validates and sanitizes search query
 * @param query - Search query to validate
 * @returns Safe search query
 */
export function sanitizeSearchQuery(query: string): string {
  if (!query || typeof query !== 'string') {
    return '';
  }

  // Remove dangerous patterns but allow legitimate search terms
  const sanitized = query
    .replace(/[<>\"'&]/g, '')
    .replace(/javascript:/gi, '')
    .replace(/on\w+\s*=/gi, '')
    .trim();

  // Limit length for search queries
  return sanitized.substring(0, 500);
}

/**
 * Validates log level input
 * @param level - Log level to validate
 * @returns True if valid log level
 */
export function validateLogLevel(level: string): boolean {
  if (!level || typeof level !== 'string') {
    return false;
  }

  const validLevels = ['error', 'warn', 'info', 'debug', 'trace', 'fatal'];
  return validLevels.includes(level.toLowerCase());
}

/**
 * Validates container name
 * @param container - Container name to validate
 * @returns True if valid container name
 */
export function validateContainerName(container: string): boolean {
  if (!container || typeof container !== 'string') {
    return false;
  }

  // Container names should be alphanumeric with hyphens and underscores
  const containerPattern = /^[a-zA-Z0-9_-]+$/;
  return containerPattern.test(container) && container.length <= 100;
}

/**
 * Validates server name
 * @param server - Server name to validate
 * @returns True if valid server name
 */
export function validateServerName(server: string): boolean {
  if (!server || typeof server !== 'string') {
    return false;
  }

  const validServers = ['prod1', 'prod2', 'staging', 'dev', 'test'];
  return validServers.includes(server.toLowerCase());
}

/**
 * Sanitizes file path to prevent directory traversal
 * @param path - File path to sanitize
 * @returns Sanitized path
 */
export function sanitizeFilePath(path: string): string {
  if (!path || typeof path !== 'string') {
    return '';
  }

  return path
    // Remove directory traversal patterns
    .replace(/\.\./g, '')
    .replace(/[\/\\]/g, '_')
    // Remove dangerous characters
    .replace(/[<>\"'&|;?*]/g, '')
    .trim();
}

/**
 * Validates and sanitizes filter values
 * @param filters - Filter object to validate
 * @returns Validated and sanitized filters
 */
export function sanitizeFilters(filters: Record<string, any>): Record<string, any> {
  const sanitized: Record<string, any> = {};

  for (const [key, value] of Object.entries(filters)) {
    if (Array.isArray(value)) {
      // Sanitize array values
      sanitized[key] = value
        .filter(item => typeof item === 'string' && validateInput(item, 100))
        .map(item => sanitizeText(item, 100));
    } else if (typeof value === 'string') {
      // Sanitize string values
      if (validateInput(value, 100)) {
        sanitized[key] = sanitizeText(value, 100);
      }
    } else if (typeof value === 'boolean' || typeof value === 'number') {
      // Allow primitive types
      sanitized[key] = value;
    }
  }

  return sanitized;
}

/**
 * Creates a safe version of data for localStorage storage
 * @param data - Data to store
 * @returns Safe string for localStorage
 */
export function createSafeStorageData(data: any): string {
  try {
    // Convert to JSON string and sanitize
    const jsonString = JSON.stringify(data);
    return sanitizeText(jsonString, 5000);
  } catch (error) {
    // Fallback to empty object
    return '{}';
  }
}

/**
 * Parses safe data from localStorage
 * @param data - Data from localStorage
 * @returns Parsed data or empty object
 */
export function parseSafeStorageData(data: string): any {
  if (!data || typeof data !== 'string') {
    return {};
  }

  try {
    // Validate JSON structure
    if (!data.startsWith('{') || !data.endsWith('}')) {
      return {};
    }

    // Parse and validate
    const parsed = JSON.parse(data);

    // Basic validation - ensure it's an object
    if (typeof parsed !== 'object' || parsed === null) {
      return {};
    }

    return parsed;
  } catch (error) {
    // Fallback to empty object
    return {};
  }
}

/**
 * Validates regex pattern to prevent ReDoS attacks
 * @param pattern - Regex pattern string
 * @returns True if pattern is safe
 */
export function validateRegexPattern(pattern: string): boolean {
  if (!pattern || typeof pattern !== 'string') {
    return false;
  }

  try {
    const regex = new RegExp(pattern);

    // Check complexity to prevent ReDoS
    const complexity = pattern.length + (pattern.match(/\(/g) || []).length;
    if (complexity > 100) {
      return false;
    }

    // Check for dangerous patterns
    const dangerousPatterns = [
      /\(\?\:.*\)/, // Lookaheads and backreferences
      /\(\?\=.*/, // Lookbehinds
      /\(\?\!.*/, // Negative lookaheads
      /\(\?\!.*/, // Negative lookbehinds
      /\(\?\:.*\)\)\{/, // Recursive patterns
    ];

    for (const dangerous of dangerousPatterns) {
      if (dangerous.test(pattern)) {
        return false;
      }
    }

    return true;
  } catch (error) {
    return false;
  }
}

/**
 * Creates a CSP nonce for inline scripts
 * @returns Base64-encoded nonce
 */
export function createCSPNonce(): string {
  if (typeof window !== 'undefined' && window.crypto) {
    const array = new Uint8Array(16);
    window.crypto.getRandomValues(array);
    return Buffer.from(array).toString('base64');
  }

  // Fallback for server-side
  return Math.random().toString(36).substring(2, 15);
}

/**
 * XSS prevention utility for HTML rendering
 * @param content - Content to render safely
 * @returns Safe HTML content
 */
export function escapeHtml(content: string): string {
  const div = document.createElement('div');
  div.textContent = content;
  return div.innerHTML;
}

/**
 * Validates timestamp input
 * @param timestamp - Timestamp to validate
 * @returns True if valid timestamp
 */
export function validateTimestamp(timestamp: string): boolean {
  if (!timestamp || typeof timestamp !== 'string') {
    return false;
  }

  try {
    const date = new Date(timestamp);
    return !isNaN(date.getTime()) && date.getTime() > 0;
  } catch (error) {
    return false;
  }
}

/**
 * Validates numeric input within a range
 * @param value - Value to validate
 * @param min - Minimum allowed value
 * @param max - Maximum allowed value
 * @returns True if valid
 */
export function validateNumericInput(value: string | number, min: number, max: number): boolean {
  const num = typeof value === 'string' ? parseFloat(value) : value;

  return !isNaN(num) && num >= min && num <= max;
}