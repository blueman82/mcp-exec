/**
 * API Route: List Docker Containers
 * GET /api/ssh/containers?server=prod1
 */

import { NextRequest, NextResponse } from 'next/server';
import { sshCommandManager } from '@/lib/ssh-command-manager';
import type { Container } from '@/types';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const server = searchParams.get('server');

    if (!server || !['prod1', 'prod2'].includes(server)) {
      return NextResponse.json(
        { error: 'Invalid server. Must be prod1 or prod2' },
        { status: 400 }
      );
    }

    // Ensure connected
    if (!sshCommandManager.isConnected(server)) {
      return NextResponse.json(
        { error: 'Not connected to server. Connect first.' },
        { status: 401 }
      );
    }

    // Execute docker ps command
    const command =
      "sudo docker ps --filter 'name=ketchup' --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}'";

    const { stdout, stderr } = await sshCommandManager.executeCommand(
      server,
      command
    );

    if (stderr && !stdout) {
      throw new Error(stderr);
    }

    // Parse output into Container objects
    const containers: Container[] = stdout
      .trim()
      .split('\n')
      .filter((line) => line)
      .map((line) => {
        const [name, image, status, ports] = line.split('|');
        return {
          name,
          image,
          status,
          uptime: status, // Status includes uptime info
          server: server as 'prod1' | 'prod2',
          ports: ports || undefined,
        };
      });

    return NextResponse.json({
      server,
      containers,
      count: containers.length,
    });
  } catch (error) {
    console.error('Container list error:', error);
    return NextResponse.json(
      {
        error: 'Failed to list containers',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
