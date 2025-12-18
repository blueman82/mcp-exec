/**
 * Security Tests for Auth Module
 * 
 * Tests for:
 * - SQL injection prevention in cursor-token-reader
 * - Shell command injection prevention
 * - Path traversal prevention in .env file parsing
 * - Header injection (CRLF) prevention
 * - Input validation (serverName, backend names)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { join } from 'node:path';
import { mkdirSync, writeFileSync, symlinkSync, unlinkSync, rmdirSync, existsSync } from 'node:fs';
import { tmpdir, homedir } from 'node:os';

// Import functions to test
import { parseEnvFile } from '../../packages/core/src/auth/backend-auth.js';
import { sanitizeHeaderValue, formatBackendAuthHeaders } from '../../packages/core/src/auth/pat-matcher.js';

describe('Security: cursor-token-reader', () => {
  // Note: extractCursorToken is harder to test in isolation because it requires
  // actual Cursor storage. These tests focus on the validation layer.
  
  it('should validate serverName length', async () => {
    // This test would require mocking the internal validateServerName function
    // For now, we test via the public interface indirectly
    const { extractCursorToken } = await import('../../packages/core/src/auth/cursor-token-reader.js');
    
    // Very long server name should fail
    const longName = 'a'.repeat(300);
    const result = extractCursorToken(longName);
    expect(result.success).toBe(false);
    expect(result.error).toContain('too long');
  });

  it('should reject serverName with SQL injection characters', async () => {
    const { extractCursorToken } = await import('../../packages/core/src/auth/cursor-token-reader.js');
    
    // SQL injection attempt
    const result = extractCursorToken("test'; DROP TABLE--");
    expect(result.success).toBe(false);
    expect(result.error).toContain('invalid characters');
  });

  it('should reject serverName with shell metacharacters', async () => {
    const { extractCursorToken } = await import('../../packages/core/src/auth/cursor-token-reader.js');
    
    // Shell injection attempt
    const result = extractCursorToken('$(whoami)');
    expect(result.success).toBe(false);
    expect(result.error).toContain('invalid characters');
  });

  it('should reject serverName with path traversal', async () => {
    const { extractCursorToken } = await import('../../packages/core/src/auth/cursor-token-reader.js');
    
    // Path traversal attempt
    const result = extractCursorToken('../../../etc/passwd');
    expect(result.success).toBe(false);
    expect(result.error).toContain('invalid characters');
  });

  it('should accept valid serverName', async () => {
    const { extractCursorToken } = await import('../../packages/core/src/auth/cursor-token-reader.js');
    
    // Valid server names (will fail for other reasons since Cursor isn't installed)
    const result = extractCursorToken('adobe-mcp-gateway');
    // Will fail because Cursor storage doesn't exist, but should NOT fail validation
    expect(result.error).not.toContain('invalid characters');
  });
});

describe('Security: backend-auth (path traversal)', () => {
  const testDir = join(tmpdir(), 'mcp-security-test-' + Date.now());
  const validEnvFile = join(testDir, 'valid.env');
  
  beforeEach(() => {
    // Create test directory in temp (which is typically outside home)
    mkdirSync(testDir, { recursive: true });
    writeFileSync(validEnvFile, 'TEST_KEY=test_value\n');
  });

  afterEach(() => {
    // Cleanup
    if (existsSync(validEnvFile)) unlinkSync(validEnvFile);
    if (existsSync(testDir)) rmdirSync(testDir, { recursive: true });
  });

  it('should reject path traversal attempts', () => {
    // Test with an absolute path that exists but is outside allowed dirs
    // Note: ../../etc/passwd doesn't exist so validation is bypassed for non-existent files
    // The path traversal protection kicks in when files exist
    // This is by design - we don't want to error on non-existent files
    
    // Skip on systems where /etc doesn't exist
    if (!existsSync('/etc')) {
      return;
    }
    
    // /etc is outside home and cwd, so should be rejected
    expect(() => parseEnvFile('/etc/hosts')).toThrow('must be within');
  });

  it('should reject absolute paths outside allowed directories', () => {
    // Skip on systems where /etc doesn't exist
    if (!existsSync('/etc/passwd')) {
      return;
    }
    expect(() => parseEnvFile('/etc/passwd')).toThrow('must be within');
  });

  it('should allow files within home directory', () => {
    // Create a temp file in home directory
    const homeEnvFile = join(homedir(), '.mcp-test-env-' + Date.now());
    try {
      writeFileSync(homeEnvFile, 'HOME_KEY=home_value\n');
      const result = parseEnvFile(homeEnvFile);
      expect(result).toEqual({ HOME_KEY: 'home_value' });
    } finally {
      if (existsSync(homeEnvFile)) unlinkSync(homeEnvFile);
    }
  });

  it('should allow files within current working directory', () => {
    // Create a temp file in cwd
    const cwdEnvFile = join(process.cwd(), '.mcp-test-env-' + Date.now());
    try {
      writeFileSync(cwdEnvFile, 'CWD_KEY=cwd_value\n');
      const result = parseEnvFile(cwdEnvFile);
      expect(result).toEqual({ CWD_KEY: 'cwd_value' });
    } finally {
      if (existsSync(cwdEnvFile)) unlinkSync(cwdEnvFile);
    }
  });

  it('should reject symlinks', () => {
    const symlinkPath = join(homedir(), '.mcp-symlink-test-' + Date.now());
    try {
      // Create a symlink to the test file
      symlinkSync(validEnvFile, symlinkPath);
      expect(() => parseEnvFile(symlinkPath)).toThrow('Symbolic links');
    } finally {
      if (existsSync(symlinkPath)) unlinkSync(symlinkPath);
    }
  });

  it('should reject oversized files', () => {
    const largeFile = join(homedir(), '.mcp-large-test-' + Date.now());
    try {
      // Create a file larger than 64KB
      const largeContent = 'X'.repeat(70 * 1024);
      writeFileSync(largeFile, largeContent);
      expect(() => parseEnvFile(largeFile)).toThrow('too large');
    } finally {
      if (existsSync(largeFile)) unlinkSync(largeFile);
    }
  });

  it('should return empty object for non-existent file', () => {
    const result = parseEnvFile(join(homedir(), 'nonexistent-file-' + Date.now()));
    expect(result).toEqual({});
  });
});

describe('Security: pat-matcher (header injection)', () => {
  it('should reject CRLF in header values', () => {
    expect(() => sanitizeHeaderValue('token\r\nX-Injected: yes')).toThrow('invalid characters');
  });

  it('should reject CR in header values', () => {
    expect(() => sanitizeHeaderValue('token\rinjection')).toThrow('invalid characters');
  });

  it('should reject LF in header values', () => {
    expect(() => sanitizeHeaderValue('token\ninjection')).toThrow('invalid characters');
  });

  it('should reject NULL bytes in header values', () => {
    expect(() => sanitizeHeaderValue('token\x00injection')).toThrow('invalid characters');
  });

  it('should accept valid header values', () => {
    expect(sanitizeHeaderValue('ghp_abcdef123456789012345678901234567890')).toBe('ghp_abcdef123456789012345678901234567890');
    expect(sanitizeHeaderValue('Bearer eyJhbGciOiJIUzI1NiJ9.test')).toBe('Bearer eyJhbGciOiJIUzI1NiJ9.test');
  });
});

describe('Security: pat-matcher (backend name validation)', () => {
  it('should accept known backends', () => {
    const result = formatBackendAuthHeaders({ jira: 'token123' });
    expect(result).toHaveProperty('X-Backend-Auth-Jira', 'token123');
  });

  it('should accept valid custom backend names', () => {
    const result = formatBackendAuthHeaders({ customservice: 'token456' });
    expect(result).toHaveProperty('X-Backend-Auth-Customservice', 'token456');
  });

  it('should reject backend names starting with number', () => {
    expect(() => formatBackendAuthHeaders({ '1invalid': 'token' })).toThrow('must start with a letter');
  });

  it('should reject backend names with invalid characters', () => {
    expect(() => formatBackendAuthHeaders({ 'in valid': 'token' })).toThrow('invalid characters');
    expect(() => formatBackendAuthHeaders({ 'in/valid': 'token' })).toThrow('invalid characters');
  });

  it('should reject empty backend name', () => {
    expect(() => formatBackendAuthHeaders({ '': 'token' })).toThrow('1-64 characters');
  });

  it('should reject very long backend names', () => {
    const longName = 'a'.repeat(100);
    expect(() => formatBackendAuthHeaders({ [longName]: 'token' })).toThrow('1-64 characters');
  });

  it('should validate header values in formatBackendAuthHeaders', () => {
    // CRLF injection via backend auth should be caught
    expect(() => formatBackendAuthHeaders({ jira: 'token\r\nX-Injected: yes' })).toThrow('invalid characters');
  });
});
