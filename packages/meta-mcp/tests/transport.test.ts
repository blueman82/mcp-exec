import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import {
  TransportMode,
  TransportConfig,
  DEFAULT_HTTP_PORT,
  DEFAULT_HTTP_HOST,
  parseTransportConfig,
} from '../src/transport.js';

describe('Transport Configuration', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    // Reset environment before each test
    process.env = { ...originalEnv };
    delete process.env.META_MCP_TRANSPORT;
    delete process.env.META_MCP_HTTP_PORT;
    delete process.env.META_MCP_HTTP_HOST;
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  describe('TransportMode enum', () => {
    it('should have STDIO mode with value "stdio"', () => {
      expect(TransportMode.STDIO).toBe('stdio');
    });

    it('should have HTTP mode with value "http"', () => {
      expect(TransportMode.HTTP).toBe('http');
    });
  });

  describe('Default constants', () => {
    it('should have DEFAULT_HTTP_PORT as 3000', () => {
      expect(DEFAULT_HTTP_PORT).toBe(3000);
    });

    it('should have DEFAULT_HTTP_HOST as "127.0.0.1"', () => {
      expect(DEFAULT_HTTP_HOST).toBe('127.0.0.1');
    });
  });

  describe('parseTransportConfig', () => {
    describe('transport mode parsing', () => {
      it('should default to stdio when no env var set', () => {
        const config = parseTransportConfig();
        expect(config.mode).toBe(TransportMode.STDIO);
      });

      it('should return stdio mode when META_MCP_TRANSPORT=stdio', () => {
        process.env.META_MCP_TRANSPORT = 'stdio';
        const config = parseTransportConfig();
        expect(config.mode).toBe(TransportMode.STDIO);
      });

      it('should return http mode when META_MCP_TRANSPORT=http', () => {
        process.env.META_MCP_TRANSPORT = 'http';
        const config = parseTransportConfig();
        expect(config.mode).toBe(TransportMode.HTTP);
      });

      it('should be case-insensitive for transport mode', () => {
        process.env.META_MCP_TRANSPORT = 'HTTP';
        const config = parseTransportConfig();
        expect(config.mode).toBe(TransportMode.HTTP);

        process.env.META_MCP_TRANSPORT = 'Http';
        const config2 = parseTransportConfig();
        expect(config2.mode).toBe(TransportMode.HTTP);
      });

      it('should fall back to stdio for invalid transport mode', () => {
        const stderrSpy = vi
          .spyOn(process.stderr, 'write')
          .mockImplementation(() => true);

        process.env.META_MCP_TRANSPORT = 'invalid';
        const config = parseTransportConfig();
        expect(config.mode).toBe(TransportMode.STDIO);
        expect(stderrSpy).toHaveBeenCalledWith(
          expect.stringContaining('Invalid META_MCP_TRANSPORT')
        );

        stderrSpy.mockRestore();
      });
    });

    describe('port parsing', () => {
      it('should default to 3000 when no env var set', () => {
        const config = parseTransportConfig();
        expect(config.port).toBe(DEFAULT_HTTP_PORT);
      });

      it('should parse valid port from META_MCP_HTTP_PORT', () => {
        process.env.META_MCP_HTTP_PORT = '8080';
        const config = parseTransportConfig();
        expect(config.port).toBe(8080);
      });

      it('should accept port 1', () => {
        process.env.META_MCP_HTTP_PORT = '1';
        const config = parseTransportConfig();
        expect(config.port).toBe(1);
      });

      it('should accept port 65535', () => {
        process.env.META_MCP_HTTP_PORT = '65535';
        const config = parseTransportConfig();
        expect(config.port).toBe(65535);
      });

      it('should fall back to default for invalid port', () => {
        const stderrSpy = vi
          .spyOn(process.stderr, 'write')
          .mockImplementation(() => true);

        process.env.META_MCP_HTTP_PORT = 'invalid';
        const config = parseTransportConfig();
        expect(config.port).toBe(DEFAULT_HTTP_PORT);
        expect(stderrSpy).toHaveBeenCalledWith(
          expect.stringContaining('Invalid META_MCP_HTTP_PORT')
        );

        stderrSpy.mockRestore();
      });

      it('should fall back to default for port 0', () => {
        const stderrSpy = vi
          .spyOn(process.stderr, 'write')
          .mockImplementation(() => true);

        process.env.META_MCP_HTTP_PORT = '0';
        const config = parseTransportConfig();
        expect(config.port).toBe(DEFAULT_HTTP_PORT);

        stderrSpy.mockRestore();
      });

      it('should fall back to default for port > 65535', () => {
        const stderrSpy = vi
          .spyOn(process.stderr, 'write')
          .mockImplementation(() => true);

        process.env.META_MCP_HTTP_PORT = '65536';
        const config = parseTransportConfig();
        expect(config.port).toBe(DEFAULT_HTTP_PORT);

        stderrSpy.mockRestore();
      });

      it('should fall back to default for negative port', () => {
        const stderrSpy = vi
          .spyOn(process.stderr, 'write')
          .mockImplementation(() => true);

        process.env.META_MCP_HTTP_PORT = '-1';
        const config = parseTransportConfig();
        expect(config.port).toBe(DEFAULT_HTTP_PORT);

        stderrSpy.mockRestore();
      });
    });

    describe('host parsing', () => {
      it('should default to 127.0.0.1 when no env var set', () => {
        const config = parseTransportConfig();
        expect(config.host).toBe(DEFAULT_HTTP_HOST);
      });

      it('should parse host from META_MCP_HTTP_HOST', () => {
        process.env.META_MCP_HTTP_HOST = '0.0.0.0';
        const config = parseTransportConfig();
        expect(config.host).toBe('0.0.0.0');
      });

      it('should accept localhost', () => {
        process.env.META_MCP_HTTP_HOST = 'localhost';
        const config = parseTransportConfig();
        expect(config.host).toBe('localhost');
      });

      it('should accept any string host value', () => {
        process.env.META_MCP_HTTP_HOST = 'my-custom-host.local';
        const config = parseTransportConfig();
        expect(config.host).toBe('my-custom-host.local');
      });
    });

    describe('combined configuration', () => {
      it('should parse all values together for HTTP mode', () => {
        process.env.META_MCP_TRANSPORT = 'http';
        process.env.META_MCP_HTTP_PORT = '8080';
        process.env.META_MCP_HTTP_HOST = '0.0.0.0';

        const config = parseTransportConfig();

        expect(config).toEqual({
          mode: TransportMode.HTTP,
          port: 8080,
          host: '0.0.0.0',
        });
      });

      it('should return complete config even for stdio mode', () => {
        process.env.META_MCP_TRANSPORT = 'stdio';
        process.env.META_MCP_HTTP_PORT = '9000';
        process.env.META_MCP_HTTP_HOST = 'localhost';

        const config = parseTransportConfig();

        expect(config).toEqual({
          mode: TransportMode.STDIO,
          port: 9000,
          host: 'localhost',
        });
      });
    });
  });

  describe('TransportConfig interface', () => {
    it('should allow optional sessionIdGenerator', () => {
      const config: TransportConfig = {
        mode: TransportMode.HTTP,
        port: 3000,
        host: '127.0.0.1',
        sessionIdGenerator: () => 'test-session-id',
      };

      expect(config.sessionIdGenerator).toBeDefined();
      expect(config.sessionIdGenerator!()).toBe('test-session-id');
    });
  });
});
