/**
 * API Route: SSH Connection with Okta 2FA
 * POST /api/ssh/connect
 */

import { NextRequest, NextResponse } from 'next/server';
import { sshCommandManager } from '@/lib/ssh-command-manager';

export async function POST(request: NextRequest) {
  try {
    const { server } = await request.json();

    if (!server || !['prod1', 'prod2'].includes(server)) {
      return NextResponse.json(
        { error: 'Invalid server. Must be prod1 or prod2' },
        { status: 400 }
      );
    }

    // Check if already connected
    if (sshCommandManager.isConnected(server)) {
      return NextResponse.json({
        status: 'connected',
        server,
        message: 'Already connected',
      });
    }

    // Initiate connection in background (non-blocking for async polling)
    // Frontend will poll /api/ssh/connect/status to track progress
    sshCommandManager.connectInBackground(server);

    const connectionStatus = sshCommandManager.getConnectionStatus(server);

    return NextResponse.json({
      server,
      ...connectionStatus,
      message: 'Connection initiated. Poll /api/ssh/connect/status for updates.',
    });
  } catch (error) {
    console.error('SSH connection error:', error);
    return NextResponse.json(
      {
        error: 'Failed to connect',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const server = searchParams.get('server');

    if (!server) {
      return NextResponse.json(
        { error: 'Server parameter required' },
        { status: 400 }
      );
    }

    sshCommandManager.disconnect(server);

    return NextResponse.json({
      status: 'disconnected',
      server,
      message: 'SSH connection closed',
    });
  } catch (error) {
    console.error('SSH disconnect error:', error);
    return NextResponse.json(
      { error: 'Failed to disconnect' },
      { status: 500 }
    );
  }
}
