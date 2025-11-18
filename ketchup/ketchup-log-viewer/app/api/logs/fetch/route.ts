/**
 * API Route: Fetch Docker Container Logs (Batch)
 * GET /api/logs/fetch?container=ketchup-app-1&server=prod1&tail=1000&since=1h
 *
 * SECURITY: All user inputs are validated to prevent command injection attacks
 * PERFORMANCE: Optimized for batch log retrieval with proper error handling
 */

import { NextRequest } from 'next/server';
import { sshCommandManager } from '@/lib/ssh-command-manager';
import { InputValidator } from '@/lib/input-validator';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

  try {
    // SECURITY LAYER 1: Validate server parameter
    const serverParam = searchParams.get('server');
    if (!serverParam) {
      return new Response(
        JSON.stringify({ error: 'Server parameter is required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const serverValidation = InputValidator.validateServerName(serverParam);
    if (!serverValidation.valid) {
      return new Response(
        JSON.stringify({ error: serverValidation.error }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }
    const server = serverParam as 'prod1' | 'prod2';

    // SECURITY LAYER 2: Validate container parameter (CRITICAL - prevents RCE)
    const containerParam = searchParams.get('container');
    if (!containerParam) {
      return new Response(
        JSON.stringify({ error: 'Container parameter is required' }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }

    const containerValidation = InputValidator.validateContainerName(containerParam);
    if (!containerValidation.valid) {
      return new Response(
        JSON.stringify({ error: containerValidation.error }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }
    const container = containerParam;

    // SECURITY LAYER 3: Validate tail parameter (CRITICAL - prevents RCE)
    const tailParam = searchParams.get('tail') || '1000';
    const tailValidation = InputValidator.validateTailParameter(tailParam);
    if (!tailValidation.valid) {
      return new Response(
        JSON.stringify({ error: tailValidation.error }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }
    const tail = tailValidation.value!;

    // SECURITY LAYER 4: Validate since parameter (optional time filter)
    const sinceParam = searchParams.get('since') || '24h';
    const sinceValidation = InputValidator.validateSinceParameter(sinceParam);
    if (!sinceValidation.valid) {
      return new Response(
        JSON.stringify({ error: sinceValidation.error }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      );
    }
    const since = sinceValidation.value;

    // Check SSH connection status
    if (!sshCommandManager.isConnected(server)) {
      return new Response(
        JSON.stringify({ error: 'Not connected to server' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Build Docker logs command - using validated inputs (safe from command injection)
    // --timestamps: Get Docker timestamps which we'll convert to ISO format
    // --tail: Limit number of lines (validated integer 1-10000)
    // --since: Time filter (validated format like 1h, 30m, 24h)
    const command = `sudo docker logs --timestamps --tail ${tail} --since=${since} ${container}`;

    // Execute command via SSH
    let result: { stdout: string; stderr: string };
    try {
      result = await sshCommandManager.executeCommand(server, command);
    } catch (error) {
      return new Response(
        JSON.stringify({
          error: 'Failed to fetch logs',
          details: error instanceof Error ? error.message : 'Unknown error',
          container,
          server
        }),
        { status: 500, headers: { 'Content-Type': 'application/json' } }
      );
    }

    // Parse and format logs to match LogLine interface
    const logs = parseDockerLogs(result.stdout || '', container, server);

    return new Response(
      JSON.stringify({
        success: true,
        data: logs,
        count: logs.length,
        container,
        server,
        tail,
        since
      }),
      {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Cache-Control': 'public, max-age=30', // Cache for 30 seconds
        }
      }
    );

  } catch (error) {
    console.error('API:fetch-logs error:', error);
    return new Response(
      JSON.stringify({
        error: 'Internal server error',
        message: error instanceof Error ? error.message : 'Unknown error'
      }),
      { status: 500, headers: { 'Content-Type': 'application/json' } }
    );
  }
}

/**
 * Parse Docker logs output into LogLine objects
 * Docker logs format: "2023-10-15T10:30:45.123456789Z log message"
 */
function parseDockerLogs(rawLogs: string, container: string, server: string) {
  const lines = rawLogs.split('\n').filter(line => line.trim());
  const logs = [];

  // Log level regex patterns (common patterns in application logs)
  const logLevelPatterns = {
    error: /\b(ERROR|FATAL|CRITICAL|ERR)\b/i,
    warn: /\b(WARN|WARNING)\b/i,
    info: /\b(INFO|INFORMATION)\b/i,
    debug: /\b(DEBUG|DBG)\b/i,
    trace: /\b(TRACE|TRACEBACK)\b/i,
  };

  for (const line of lines) {
    try {
      // Extract timestamp and content from Docker log format
      const timestampMatch = line.match(/^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)\s*(.*)$/);

      if (!timestampMatch) {
        // Skip malformed lines
        continue;
      }

      const [, rawTimestamp, content] = timestampMatch;

      // Parse Docker timestamp to ISO format (it's already ISO, just keep it)
      const timestamp = new Date(rawTimestamp).toISOString();

      // Detect log level from content
      let level = 'none'; // default level
      for (const [detectedLevel, pattern] of Object.entries(logLevelPatterns)) {
        if (pattern.test(content)) {
          level = detectedLevel;
          break;
        }
      }

      // Create LogLine object matching the interface from types/index.ts
      const logLine = {
        timestamp,
        content: content.trim(),
        container,
        server,
        level: level as 'error' | 'warn' | 'info' | 'debug' | 'trace' | 'none',
      };

      logs.push(logLine);
    } catch (error) {
      // Skip lines that can't be parsed but continue processing others
      console.warn('Failed to parse log line:', line, error);
      continue;
    }
  }

  return logs;
}