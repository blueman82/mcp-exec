/**
 * MetricsOverlay Component
 * Displays performance metrics for log streaming (throughput, total, filtered, uptime)
 */

'use client';

import React from 'react';

interface MetricsOverlayProps {
  logsPerSecond: number;
  totalLogs: number;
  filteredLogs: number;
  connectionStartTime: Date | null;
  connectedCount: number;
}

const MetricsOverlay: React.FC<MetricsOverlayProps> = ({
  logsPerSecond,
  totalLogs,
  filteredLogs,
  connectionStartTime,
  connectedCount,
}) => {
  const formatUptime = (startTime: Date | null): string => {
    if (!startTime) return '--';

    const uptime = Math.floor((Date.now() - startTime.getTime()) / 1000);
    const hours = Math.floor(uptime / 3600);
    const minutes = Math.floor((uptime % 3600) / 60);
    const seconds = uptime % 60;

    return hours > 0
      ? `${hours}h ${minutes}m`
      : minutes > 0
      ? `${minutes}m ${seconds}s`
      : `${seconds}s`;
  };

  const filterPercentage =
    totalLogs > 0 ? Math.round((filteredLogs / totalLogs) * 100) : 0;

  return (
    <div className="p-4 bg-gradient-to-r from-purple-900 to-indigo-900 border-b border-purple-700">
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
          <div className="text-xs text-purple-300 mb-1">Throughput</div>
          <div className="text-2xl font-bold text-white">{logsPerSecond}</div>
          <div className="text-xs text-purple-400">logs/sec</div>
        </div>

        <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
          <div className="text-xs text-purple-300 mb-1">Total Logs</div>
          <div className="text-2xl font-bold text-white">{totalLogs.toLocaleString()}</div>
          <div className="text-xs text-purple-400">lines</div>
        </div>

        <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
          <div className="text-xs text-purple-300 mb-1">Filtered</div>
          <div className="text-2xl font-bold text-white">{filteredLogs.toLocaleString()}</div>
          <div className="text-xs text-purple-400">{filterPercentage}%</div>
        </div>

        <div className="bg-black bg-opacity-30 p-3 rounded border border-purple-600">
          <div className="text-xs text-purple-300 mb-1">Uptime</div>
          <div className="text-2xl font-bold text-white">{formatUptime(connectionStartTime)}</div>
          <div className="text-xs text-purple-400">
            {connectedCount > 0 ? 'connected' : 'disconnected'}
          </div>
        </div>
      </div>
    </div>
  );
};

export default MetricsOverlay;
