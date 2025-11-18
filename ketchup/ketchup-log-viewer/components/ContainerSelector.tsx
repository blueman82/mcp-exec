/**
 * ContainerSelector Component
 * Multi-select grid for choosing containers to monitor
 */

'use client';

import { useEffect, useState } from 'react';
import { parseHealthStatus, getHealthInfo } from '@/lib/health-status-parser';
import { extractVersion, getVersionDisplay } from '@/lib/version-extractor';
import type { Container } from '@/types';

interface ContainerSelectorProps {
  servers: ('prod1' | 'prod2')[]; // Multi-server support
  onSelectionChange: (selections: { container: string; server: 'prod1' | 'prod2' }[]) => void;
  selectedContainers: { container: string; server: 'prod1' | 'prod2' }[];
  theme: 'dark' | 'light';
}

type ServerLoadingState = {
  [key in 'prod1' | 'prod2']?: boolean;
};

type ServerErrorState = {
  [key in 'prod1' | 'prod2']?: string;
};

type CollapsedState = {
  [key in 'prod1' | 'prod2']: boolean;
};

export default function ContainerSelector({
  servers,
  onSelectionChange,
  selectedContainers,
  theme,
}: ContainerSelectorProps) {
  const [containers, setContainers] = useState<Container[]>([]);
  const [loadingStates, setLoadingStates] = useState<ServerLoadingState>({});
  const [errorStates, setErrorStates] = useState<ServerErrorState>({});
  const [collapsed, setCollapsed] = useState<CollapsedState>({ prod1: false, prod2: false });

  // Fetch containers from multiple servers
  useEffect(() => {
    const fetchContainers = async () => {
      // Set all servers to loading
      const initialLoadingStates: ServerLoadingState = {};
      servers.forEach(server => {
        initialLoadingStates[server] = true;
      });
      setLoadingStates(initialLoadingStates);
      setErrorStates({});

      try {
        // Fetch from all servers concurrently
        const fetchPromises = servers.map(async (server) => {
          try {
            const response = await fetch(`/api/ssh/containers?server=${server}`);

            if (!response.ok) {
              throw new Error(`Failed to fetch from ${server}`);
            }

            const data = await response.json();
            // Ensure each container has server attribution
            return data.containers.map((c: Container) => ({
              ...c,
              server,
            }));
          } catch (err) {
            // Store error for this server
            setErrorStates(prev => ({
              ...prev,
              [server]: err instanceof Error ? err.message : 'Unknown error',
            }));
            return [];
          } finally {
            // Mark this server as done loading
            setLoadingStates(prev => ({
              ...prev,
              [server]: false,
            }));
          }
        });

        const results = await Promise.all(fetchPromises);
        // Flatten all container arrays
        const allContainers = results.flat();
        setContainers(allContainers);
      } catch (err) {
        console.error('Error fetching containers:', err);
      }
    };

    if (servers.length > 0) {
      fetchContainers();
    }
  }, [servers]);

  const toggleContainer = (containerName: string, server: 'prod1' | 'prod2') => {
    const isSelected = selectedContainers.some(
      (sel) => sel.container === containerName && sel.server === server
    );

    const newSelection = isSelected
      ? selectedContainers.filter(
          (sel) => !(sel.container === containerName && sel.server === server)
        )
      : [...selectedContainers, { container: containerName, server }];

    onSelectionChange(newSelection);
  };

  const selectAll = () => {
    const allSelections = containers.map((c) => ({
      container: c.name,
      server: c.server,
    }));
    onSelectionChange(allSelections);
  };

  const clearAll = () => {
    onSelectionChange([]);
  };

  const selectAllForServer = (server: 'prod1' | 'prod2') => {
    const serverContainers = containers
      .filter((c) => c.server === server)
      .map((c) => ({ container: c.name, server: c.server }));

    // Merge with existing selections from other servers
    const otherSelections = selectedContainers.filter((sel) => sel.server !== server);
    onSelectionChange([...otherSelections, ...serverContainers]);
  };

  const clearAllForServer = (server: 'prod1' | 'prod2') => {
    const newSelection = selectedContainers.filter((sel) => sel.server !== server);
    onSelectionChange(newSelection);
  };

  const toggleServerCollapse = (server: 'prod1' | 'prod2') => {
    setCollapsed(prev => ({ ...prev, [server]: !prev[server] }));
  };

  // Group containers by server
  const containersByServer = servers.reduce((acc, server) => {
    acc[server] = containers.filter((c) => c.server === server);
    return acc;
  }, {} as Record<'prod1' | 'prod2', Container[]>);

  // Check if all servers are still loading
  const allLoading = servers.every(server => loadingStates[server] === true);

  // Server badge color mapping
  const serverBadgeColors = {
    prod1: 'bg-blue-500/20 text-blue-400 border-blue-500/40',
    prod2: 'bg-green-500/20 text-green-400 border-green-500/40',
  };

  if (allLoading) {
    return (
      <div className="flex items-center justify-center p-8">
        <div className="text-gray-400">Loading containers from {servers.join(', ')}...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Global Header */}
      <div className="flex items-center justify-between">
        <h3 className={`text-lg font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
          Containers ({containers.length} total)
        </h3>
        <div className="flex space-x-3">
          <button
            onClick={selectAll}
            className="px-4 py-2 text-sm bg-cyan-500 hover:bg-cyan-400 text-black font-medium rounded-lg transition-all duration-200"
          >
            Select All
          </button>
          <button
            onClick={clearAll}
            className={`px-4 py-2 text-sm ${
              theme === 'dark' ? 'bg-white/5 hover:bg-white/10 text-white border-white/10' : 'bg-gray-200 hover:bg-gray-300 text-gray-900 border-gray-300'
            } font-medium rounded-lg border transition-all duration-200`}
          >
            Clear All
          </button>
        </div>
      </div>

      {/* Server Groups */}
      {servers.map((server) => {
        const serverContainers = containersByServer[server] || [];
        const serverLoading = loadingStates[server];
        const serverError = errorStates[server];
        const isCollapsed = collapsed[server];
        const selectedCount = selectedContainers.filter(sel => sel.server === server).length;

        return (
          <div key={server} className="space-y-3">
            {/* Server Group Header */}
            <div className="flex items-center justify-between p-4 bg-white/[0.02] border border-white/10 rounded-lg">
              <div className="flex items-center gap-3">
                <button
                  onClick={() => toggleServerCollapse(server)}
                  className={`${theme === 'dark' ? 'text-white hover:text-cyan-400' : 'text-gray-900 hover:text-blue-600'} transition-colors`}
                >
                  <svg
                    className={`w-5 h-5 transform transition-transform ${isCollapsed ? '-rotate-90' : ''}`}
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                <h4 className={`text-md font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
                  {server} Containers ({serverContainers.length})
                </h4>
                {selectedCount > 0 && (
                  <span className="text-xs text-gray-400 ml-2">
                    {selectedCount} selected
                  </span>
                )}
              </div>
              <div className="space-x-2">
                <button
                  onClick={() => selectAllForServer(server)}
                  className="px-3 py-1.5 text-xs bg-cyan-500/20 hover:bg-cyan-500/30 text-cyan-400 font-medium rounded-md transition-all duration-200"
                  disabled={serverContainers.length === 0}
                >
                  Select All
                </button>
                <button
                  onClick={() => clearAllForServer(server)}
                  className={`px-3 py-1.5 text-xs ${
                    theme === 'dark' ? 'bg-white/5 hover:bg-white/10 text-white border-white/10' : 'bg-gray-200 hover:bg-gray-300 text-gray-900 border-gray-300'
                  } font-medium rounded-md border transition-all duration-200`}
                >
                  Clear
                </button>
              </div>
            </div>

            {/* Server Content */}
            {!isCollapsed && (
              <>
                {serverLoading && (
                  <div className="p-4 text-gray-400 text-sm">
                    Loading containers from {server}...
                  </div>
                )}

                {serverError && (
                  <div className="p-4 bg-red-900/20 border border-red-700/40 text-red-300 rounded text-sm">
                    Error loading {server}: {serverError}
                  </div>
                )}

                {!serverLoading && !serverError && serverContainers.length === 0 && (
                  <div className="p-4 text-gray-500 text-sm">
                    No containers found on {server}
                  </div>
                )}

                {serverContainers.length > 0 && (
                  <div className="grid gap-6" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))' }}>
                    {serverContainers.map((container) => {
                      const isSelected = selectedContainers.some(
                        (sel) => sel.container === container.name && sel.server === server
                      );
                      const healthStatus = parseHealthStatus(container.status);
                      const healthInfo = getHealthInfo(healthStatus);
                      const version = extractVersion(container.image);
                      const versionDisplay = getVersionDisplay(version);

                      return (
                        <div
                          key={`${server}-${container.name}`}
                          onClick={() => toggleContainer(container.name, server)}
                          className={`p-6 rounded-lg cursor-pointer transition-all duration-200 ${
                            isSelected
                              ? 'bg-white/[0.02] border border-cyan-500 shadow-lg'
                              : 'bg-white/[0.01] border border-white/10 hover:border-white/20 hover:bg-white/[0.02]'
                          }`}
                        >
                          {/* Header row: checkbox + server badge */}
                          <div className="flex items-center justify-between mb-3">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="w-4 h-4 text-blue-600"
                            />
                            <div className="flex items-center gap-2">
                              {/* Server Badge */}
                              <div className={`px-2 py-1 rounded text-xs font-bold border ${serverBadgeColors[server]}`}>
                                {server}
                              </div>
                              {/* Health Badge */}
                              <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium ${
                                healthStatus === 'healthy'
                                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                  : healthStatus === 'unhealthy'
                                  ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                  : 'bg-gray-500/10 text-gray-400 border border-gray-500/20'
                              }`}>
                                <span>{healthInfo.icon}</span>
                                <span>{healthInfo.label}</span>
                              </div>
                            </div>
                          </div>

                          {/* Container name - full width */}
                          <div className={`font-mono text-lg font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'} tracking-tight mb-3 break-words`}>
                            {container.name.replace('ketchup-', '')}
                          </div>

                          {/* Version info */}
                          <div className="text-sm font-mono font-medium text-cyan-400 mb-3">
                            {versionDisplay.text}
                          </div>

                          {/* Status info - subtle */}
                          <div className="text-sm text-gray-500">
                            {container.status.split(' ').slice(0, 3).join(' ')}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </>
            )}
          </div>
        );
      })}

      {/* Global Selected count */}
      {selectedContainers.length > 0 && (
        <div className="text-sm text-gray-400 pt-2">
          {selectedContainers.length} container
          {selectedContainers.length !== 1 ? 's' : ''} selected across all servers
        </div>
      )}
    </div>
  );
}
