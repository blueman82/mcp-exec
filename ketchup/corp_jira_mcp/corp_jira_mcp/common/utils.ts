import { fetch, Response } from 'undici';
import { writeFileSync } from 'fs';
import { getUserAgent } from "universal-user-agent";
import { VERSION } from "./version.js";
import { config } from "./config.js";
import { createJiraError } from "./errors.js";
import '../env.js';
import { dirname } from 'path';
import { existsSync, mkdirSync } from 'fs';

type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function parseResponseBody(response: Response): Promise<unknown> {
  // Handle 204 No Content responses
  if (response.status === 204) {
    return { success: true };
  }

  const contentType = response.headers.get("content-type");
  if (contentType?.includes("application/json")) {
    const text = await response.text();
    if (!text) {
      return { success: true };
    }
    try {
      return JSON.parse(text);
    } catch (error) {
      logToFile(`Failed to parse JSON response: ${error}`);
      return { success: true };
    }
  }
  if (contentType?.includes("application/xml")) {
    const text = await response.text();
    logToFile(`Received XML response: ${text}`);
    throw new Error(`Received XML response instead of JSON. This usually indicates an authentication or API endpoint issue.`);
  }
  return response.text();
}

export function buildUrl(path: string, params: Record<string, string | number | undefined>): string {
  // Ensure path doesn't start with a slash
  const cleanPath = path.replace(/^\//, '');
  const url = new URL(`${config.apiBaseUrl}/${cleanPath}`);

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      url.searchParams.append(key, value.toString());
    }
  });
  return url.toString();
}

const USER_AGENT = `modelcontextprotocol/servers/jira/v${VERSION} ${getUserAgent()}`;

// Global variable to store the incoming Authorization header token
let currentAuthToken: string | undefined;

/**
 * Set the current authorization token from incoming request
 * This should be called by the MCP server before processing each request
 */
export function setCurrentAuthToken(token: string | undefined): void {
  currentAuthToken = token;
  if (token) {
    logToFile('Authorization token set from incoming request');
  }
}

// Add interface for the function type with hasLoggedPath property
interface LogFunction {
  (message: string): void;
  hasLoggedPath?: boolean;
}

// Define the logging function with proper typing
const logToFile: LogFunction = (message: string) => {
  try {
    const timestamp = new Date().toISOString();
    const logMessage = `${timestamp}: ${message}\n`;
    
    // Create directory if it doesn't exist
    const dir = dirname(config.logFile);
    if (!existsSync(dir)) {
      mkdirSync(dir, { recursive: true });
    }
    
    writeFileSync(config.logFile, logMessage, { flag: 'a' });

    // Log path on first write
    if (!logToFile.hasLoggedPath) {
      console.error(`Writing logs to: ${config.logFile}`);
      logToFile.hasLoggedPath = true;
    }
  } catch (error) {
    // Fallback to console if file writing fails
    console.error(`Failed to write to log file (${config.logFile}): ${error}`);
    console.error(message);
  }
};

// Initialize the hasLoggedPath property
logToFile.hasLoggedPath = false;

/**
 * Verifies authentication with Jira API
 * @returns The current user information if authenticated
 * @throws Error if authentication fails
 */
export async function verifyAuthentication(): Promise<unknown> {
  logToFile("Verifying Jira authentication...");
  return jiraRequest("myself");
}

function constructAuthHeader(email: string, token: string): string {
  // Simplified auth header construction - just use email:token format
  const authString = `${email}:${token}`;
  logToFile('Constructing basic auth header with email:token format');
  return `Basic ${Buffer.from(authString).toString('base64')}`;
}

/**
 * Constructs headers for iPaaS authentication
 * @param imsToken The IMS token for authentication
 * @param apiKey The API key for iPaaS
 * @param username Optional username for iPaaS
 * @param password Optional password for iPaaS
 * @returns Headers object with iPaaS authentication
 */
function constructIpaasHeaders(
  imsToken: string,
  apiKey: string,
  username?: string,
  password?: string
): Record<string, string> {
  const headers: Record<string, string> = {
    "Authorization": `${imsToken}`,
    "Api_key": apiKey,
    "Content-Type": "application/json"
  };

  // Add optional username and password if provided
  if (username) {
    headers["Username"] = username;
  }
  
  if (password) {
    headers["Password"] = password;
  }

  logToFile('Constructing iPaaS headers with IMS token and API key');
  return headers;
}

export async function jiraRequest(
  path: string,
  options: RequestOptions = {}
): Promise<unknown> {
  let headers: Record<string, string>;
  
  // Determine which authentication method to use based on config
  if (config.useIpaas) {
    // iPaaS authentication
    
    // First, try to use the token from the incoming request
    if (currentAuthToken) {
      logToFile('Using token from incoming request Authorization header');
      
      // Extract token from "Bearer " prefix if present
      const token = currentAuthToken.startsWith('Bearer ') 
        ? currentAuthToken.substring(7) 
        : currentAuthToken;
      
      headers = {
        ...constructIpaasHeaders(
          token,
          config.auth.apiKey || '',
          config.auth.username,
          config.auth.password
        ),
        ...options.headers
      };
    } else {
      // Fallback to environment variables if no incoming token
      logToFile('No incoming token, falling back to environment variables');
      const { imsToken, apiKey, username, password } = config.auth;
      
      if (!imsToken || !apiKey) {
        throw new Error("IMS token and API key are required for iPaaS authentication");
      }
      
      headers = {
        ...constructIpaasHeaders(imsToken, apiKey, username, password),
        ...options.headers
      };
    }
  } else {
    // Direct Jira authentication
    headers = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    ...options.headers,
  };

  // Get auth details from config
  const { email, token } = config.auth;
  if (!email || !token) {
      throw new Error("Email and token are required for direct authentication");
  }

  // Construct auth header using simplified approach
  headers["Authorization"] = constructAuthHeader(email, token);
  }

  // Build URL
  const url = path.startsWith('http') ? path : buildUrl(path, {});

  logToFile(`Making request to: ${url}`);
  logToFile(`Method: ${options.method || "GET"}`);
  logToFile(`Headers: ${JSON.stringify({
    ...headers, 
    Authorization: '[REDACTED]',
    Api_key: headers.Api_key ? '[REDACTED]' : undefined,
    Password: headers.Password ? '[REDACTED]' : undefined
  }, null, 2)}`);
  
  if (options.body) {
    logToFile(`Request body: ${JSON.stringify(options.body, null, 2)}`);
  }

  try {
    const response = await fetch(url, {
      method: options.method || "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
      // Add timeout and other configuration for Adobe infrastructure
      signal: AbortSignal.timeout(config.timeout || 30000),
    });

    logToFile(`Response status: ${response.status} ${response.statusText}`);
    logToFile(`Response headers: ${JSON.stringify(Object.fromEntries(response.headers.entries()), null, 2)}`);

    // For 204 No Content responses, return success
    if (response.status === 204) {
      return { success: true };
    }

    const responseBody = await parseResponseBody(response);
    
    // Log response body but redact sensitive information
    const sanitizedBody = typeof responseBody === 'object' ? 
      JSON.stringify(responseBody, (key, value) => 
        ['token', 'password', 'secret'].includes(key.toLowerCase()) ? '[REDACTED]' : value
      , 2) : responseBody;
    logToFile(`Response body: ${sanitizedBody}`);

    if (!response.ok) {
      throw createJiraError(response.status, responseBody);
    }

    return responseBody;
  } catch (error) {
    if (error instanceof Error) {
      logToFile(`Request failed: ${error.message}`);
      throw error;
    }
    throw new Error(`Unknown error occurred: ${String(error)}`);
  }
}

// ... rest of the utility functions remain the same