/**
 * Cursor Token Reader
 * 
 * Extracts OAuth tokens from Cursor's encrypted storage.
 * Cursor uses Chromium's safeStorage encryption (AES-128-CBC with PBKDF2-derived key).
 * 
 * macOS: Keychain stores the encryption password
 * Windows: DPAPI (not yet implemented)
 * Linux: gnome-keyring or kwallet (not yet implemented)
 * 
 * Security Notes:
 * - Uses execFileSync instead of execSync to prevent shell injection
 * - Input validation on serverName to prevent SQL injection
 * - Chromium's crypto parameters (SHA1, 1003 iterations, static IV) are inherited
 *   and cannot be changed without breaking compatibility with Cursor's storage
 */

import { execFileSync } from 'child_process';
import { createDecipheriv, pbkdf2Sync } from 'crypto';
import { existsSync } from 'fs';
import { homedir, platform } from 'os';
import { join } from 'path';

/**
 * Allowlist of characters permitted in server names
 * Security: Explicit set prevents regex edge cases with Unicode/locale
 */
const ALLOWED_SERVER_NAME_CHARS = new Set(
  'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_'.split('')
);

/**
 * Maximum length for server names
 */
const MAX_SERVER_NAME_LENGTH = 256;

/**
 * OAuth token data stored by Cursor
 */
export interface CursorOAuthToken {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  refresh_token?: string;
}

/**
 * Result from token extraction attempt
 */
export interface TokenExtractionResult {
  success: boolean;
  token?: CursorOAuthToken;
  error?: string;
}

// Chromium safeStorage constants
const CHROMIUM_SALT = 'saltysalt';
const CHROMIUM_ITERATIONS = 1003;
const CHROMIUM_KEY_LENGTH = 16; // AES-128
const CHROMIUM_IV = Buffer.alloc(16, ' '); // 16 space characters

/**
 * Validate server name to prevent injection attacks
 * Security: Uses allowlist instead of regex to avoid Unicode/locale edge cases
 * 
 * @throws Error if server name is invalid
 */
function validateServerName(serverName: string): void {
  if (!serverName || serverName.length === 0) {
    throw new Error('Server name is required');
  }
  if (serverName.length > MAX_SERVER_NAME_LENGTH) {
    throw new Error('Server name too long');
  }
  for (const char of serverName) {
    if (!ALLOWED_SERVER_NAME_CHARS.has(char)) {
      // Security: Don't reveal which character is invalid - aids probing
      throw new Error('Server name contains invalid characters');
    }
  }
}

/**
 * Get the path to Cursor's storage database
 * Security: Generic error message to avoid revealing system paths
 */
function getCursorDbPath(): string {
  const home = homedir();
  const os = platform();
  
  switch (os) {
    case 'darwin':
      return join(home, 'Library/Application Support/Cursor/User/globalStorage/state.vscdb');
    case 'win32':
      return join(home, 'AppData/Roaming/Cursor/User/globalStorage/state.vscdb');
    case 'linux':
      return join(home, '.config/Cursor/User/globalStorage/state.vscdb');
    default:
      // Security: Don't reveal the actual platform value
      throw new Error('This feature is only supported on macOS, Windows, and Linux');
  }
}

/**
 * Get the Chromium encryption password from the system keychain
 * Currently only supports macOS
 * 
 * Security: Uses execFileSync with argument array to prevent shell injection
 */
function getEncryptionPassword(): string {
  const os = platform();
  
  if (os !== 'darwin') {
    throw new Error('Token extraction is only supported on macOS');
  }
  
  try {
    // Get password from macOS Keychain
    // Security: execFileSync with argument array prevents shell injection
    const password = execFileSync(
      'security',
      ['find-generic-password', '-s', 'Cursor Safe Storage', '-w'],
      { encoding: 'utf-8' }
    ).trim();
    return password;
  } catch {
    throw new Error(
      'Could not retrieve Cursor encryption password from Keychain. ' +
      'Make sure Cursor has been opened at least once and you have granted Keychain access.'
    );
  }
}

/**
 * Derive the AES key from the Chromium encryption password
 */
function deriveKey(password: string): Buffer {
  return pbkdf2Sync(
    password,
    CHROMIUM_SALT,
    CHROMIUM_ITERATIONS,
    CHROMIUM_KEY_LENGTH,
    'sha1'
  );
}

/**
 * Decrypt a Chromium-encrypted value
 * The encrypted data starts with 'v10' or 'v11' version prefix
 */
function decryptValue(encryptedData: Buffer, key: Buffer): string {
  // Check for version prefix
  const prefix = encryptedData.subarray(0, 3).toString();
  if (prefix !== 'v10' && prefix !== 'v11') {
    throw new Error(`Unknown encryption version: ${prefix}`);
  }
  
  // Skip the 3-byte version prefix
  const ciphertext = encryptedData.subarray(3);
  
  // Decrypt using AES-128-CBC
  const decipher = createDecipheriv('aes-128-cbc', key, CHROMIUM_IV);
  
  let decrypted = decipher.update(ciphertext);
  decrypted = Buffer.concat([decrypted, decipher.final()]);
  
  return decrypted.toString('utf-8');
}

/**
 * Query the Cursor SQLite database for a specific key
 * 
 * Security:
 * - Uses execFileSync with argument array to prevent shell injection
 * - The key parameter is passed via stdin with proper escaping
 * - The key is constructed from validated serverName, so SQL injection
 *   is prevented at the validation layer
 */
function queryDatabase(dbPath: string, key: string): Buffer | null {
  try {
    // Security: The key is built from validated serverName (alphanumeric + -_)
    // so SQL injection is prevented. Still escape single quotes as defense-in-depth.
    const escapedKey = key.replace(/'/g, "''");
    const query = `SELECT hex(value) FROM ItemTable WHERE key = '${escapedKey}';`;
    
    // Security: execFileSync with argument array prevents shell injection
    // The dbPath comes from getCursorDbPath() which is trusted (built from homedir)
    const result = execFileSync(
      'sqlite3',
      [dbPath],
      { 
        encoding: 'utf-8', 
        maxBuffer: 10 * 1024 * 1024,
        input: query,
      }
    );
    
    if (!result || result.trim().length === 0) {
      return null;
    }
    
    // Convert hex string back to buffer
    const rawBuffer = Buffer.from(result.trim(), 'hex');
    
    // Check if this is a serialized Node.js Buffer ({"type":"Buffer","data":[...]})
    const rawString = rawBuffer.toString('utf-8');
    if (rawString.startsWith('{"type":"Buffer"')) {
      try {
        const parsed = JSON.parse(rawString) as { type: string; data: number[] };
        return Buffer.from(parsed.data);
      } catch {
        // Not valid JSON, return as-is
      }
    }
    
    return rawBuffer;
  } catch {
    return null;
  }
}

/**
 * Extract OAuth token for a specific MCP server from Cursor's storage
 * 
 * @param serverName - The name of the MCP server as configured in Cursor (e.g., "adobe-mcp-gateway")
 * @returns TokenExtractionResult with the token or error
 * 
 * Security: serverName is validated to prevent SQL injection and path traversal
 * 
 * @example
 * ```ts
 * const result = extractCursorToken('adobe-mcp-gateway');
 * if (result.success && result.token) {
 *   console.log('Token:', result.token.access_token);
 * }
 * ```
 */
export function extractCursorToken(serverName: string): TokenExtractionResult {
  try {
    // Security: Validate serverName first to prevent injection attacks
    validateServerName(serverName);
    
    const dbPath = getCursorDbPath();
    
    if (!existsSync(dbPath)) {
      // Security: Generic error message - don't reveal system paths
      return {
        success: false,
        error: 'Cursor storage not found. Is Cursor installed?',
      };
    }
    
    // Get the encryption password
    const password = getEncryptionPassword();
    const key = deriveKey(password);
    
    // The key format Cursor uses for MCP tokens
    // Security: serverName is validated, so this is safe to interpolate
    const tokenKey = `secret://{"extensionId":"anysphere.cursor-mcp","key":"[user-${serverName}] mcp_tokens"}`;
    
    // Query the database
    const encryptedData = queryDatabase(dbPath, tokenKey);
    
    if (!encryptedData) {
      return {
        success: false,
        error: `No OAuth token found for server "${serverName}". Click "Connect" in Cursor first.`,
      };
    }
    
    // Decrypt the value
    const decryptedJson = decryptValue(encryptedData, key);
    
    // Parse the JSON
    const tokenData = JSON.parse(decryptedJson) as CursorOAuthToken;
    
    return {
      success: true,
      token: tokenData,
    };
  } catch (err) {
    // Security: Don't expose detailed error messages that might reveal system info
    const errorMessage = err instanceof Error ? err.message : 'Unknown error';
    // Only include error message if it's one of our known safe messages
    const safeMessages = [
      'Server name is required',
      'Server name too long',
      'Server name contains invalid characters',
      'This feature is only supported on macOS, Windows, and Linux',
      'Token extraction is only supported on macOS',
      'Could not retrieve Cursor encryption password from Keychain.',
    ];
    const isSafeMessage = safeMessages.some(safe => errorMessage.startsWith(safe));
    
    return {
      success: false,
      error: isSafeMessage ? errorMessage : 'Failed to extract Cursor token',
    };
  }
}

/**
 * Check if Cursor token extraction is supported on this platform
 */
export function isTokenExtractionSupported(): boolean {
  return platform() === 'darwin';
}

/**
 * Get the platform name for error messages
 */
export function getPlatformName(): string {
  const os = platform();
  switch (os) {
    case 'darwin': return 'macOS';
    case 'win32': return 'Windows';
    case 'linux': return 'Linux';
    default: return os;
  }
}
