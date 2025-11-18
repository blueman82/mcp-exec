/**
 * GET /api/ssh/connect/status
 * Poll connection status for async Okta 2FA flow
 */

import { NextRequest, NextResponse } from 'next/server';
import { sshCommandManager } from '@/lib/ssh-command-manager';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const server = searchParams.get('server');

  if (!server) {
    return NextResponse.json(
      { error: 'Server parameter required' },
      { status: 400 }
    );
  }

  if (server !== 'prod1' && server !== 'prod2') {
    return NextResponse.json(
      { error: 'Invalid server. Must be prod1 or prod2' },
      { status: 400 }
    );
  }

  try {
    const connectionStatus = sshCommandManager.getConnectionStatus(server);

    return NextResponse.json({
      server,
      ...connectionStatus,
    });
  } catch (error) {
    console.error('Error getting connection status:', error);
    return NextResponse.json(
      {
        error: 'Failed to get connection status',
        message: error instanceof Error ? error.message : 'Unknown error'
      },
      { status: 500 }
    );
  }
}
