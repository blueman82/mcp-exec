/**
 * API Route: Stream Docker Container Logs (SSE)
 * GET /api/logs/stream?container=ketchup-app-1&server=prod1&tail=1000
 *
 * SECURITY: All user inputs are validated to prevent command injection attacks
 */

import { NextRequest } from 'next/server';
import { sshCommandManager } from '@/lib/ssh-command-manager';
import { InputValidator } from '@/lib/input-validator';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);

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
  const container = containerParam; // Now safe to use

  // SECURITY LAYER 3: Validate tail parameter (CRITICAL - prevents RCE)
  const tailParam = searchParams.get('tail') || '1000';
  const tailValidation = InputValidator.validateTailParameter(tailParam);
  if (!tailValidation.valid) {
    return new Response(
      JSON.stringify({ error: tailValidation.error }),
      { status: 400, headers: { 'Content-Type': 'application/json' } }
    );
  }
  const tail = tailValidation.value!; // Validated integer

  // Check SSH connection status
  if (!sshCommandManager.isConnected(server)) {
    return new Response(
      JSON.stringify({ error: 'Not connected to server' }),
      { status: 401, headers: { 'Content-Type': 'application/json' } }
    );
  }

  // Create SSE stream
  const encoder = new TextEncoder();
  const stream = new ReadableStream({
    start(controller) {
      // Docker logs command - using validated inputs (safe from command injection)
      // tail is a validated integer (1-10000)
      // container is a validated string matching [a-zA-Z0-9][a-zA-Z0-9_.-]*
      const command = `sudo docker logs -f --tail ${tail} ${container}`;

      // Stream logs via SSH
      const cleanup = sshCommandManager.streamCommand(
        server,
        command,
        (data: string) => {
          // Send log data as SSE event
          const lines = data.split('\n');
          for (const line of lines) {
            if (line.trim()) {
              const sseData = `data: ${JSON.stringify({
                container,
                server,
                timestamp: new Date().toISOString(),
                content: line,
              })}\n\n`;

              controller.enqueue(encoder.encode(sseData));
            }
          }
        },
        (error: Error) => {
          // Send error as SSE event
          const sseError = `data: ${JSON.stringify({
            error: error.message,
            container,
            server,
          })}\n\n`;

          controller.enqueue(encoder.encode(sseError));
          controller.close();
        }
      );

      // Cleanup on connection close
      request.signal.addEventListener('abort', () => {
        cleanup();
        controller.close();
      });
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    },
  });
}
