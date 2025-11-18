/**
 * Main Page - Ketchup Log Viewer
 * Multi-container log monitoring with Okta 2FA SSH
 */

'use client';

import { useState, useEffect } from 'react';
import ContainerSelector from '@/components/ContainerSelector';
import MergedLogViewer from '@/components/MergedLogViewer';
import StackedLogViewer from '@/components/StackedLogViewer';
import HybridLogViewer from '@/components/HybridLogViewer';
import OktaAuthPrompt from '@/components/OktaAuthPrompt';

export default function Home() {
  const [connectedServers, setConnectedServers] = useState<Set<string>>(
    new Set()
  );
  const [selectedContainers, setSelectedContainers] = useState<
    Array<{ container: string; server: 'prod1' | 'prod2' }>
  >([]);
  const [isConnecting, setIsConnecting] = useState(false);
  const [oktaPrompt, setOktaPrompt] = useState<{
    visible: boolean;
    server: string;
  }>({ visible: false, server: '' });
  const [error, setError] = useState<string | null>(null);
  const [theme, setTheme] = useState<'dark' | 'light'>('dark');
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [layout, setLayout] = useState<'merged' | 'stacked' | 'hybrid'>('merged');
  const [sidebarWidth, setSidebarWidth] = useState(384); // 384px = w-96
  const [isResizing, setIsResizing] = useState(false);

  // Load theme preference from localStorage
  useEffect(() => {
    const storedTheme = localStorage.getItem('ketchup-log-viewer-theme') as 'dark' | 'light' | null;
    if (storedTheme) {
      setTheme(storedTheme);
    }
  }, []);

  // Load saved container selections from localStorage
  useEffect(() => {
    const storedSelections = localStorage.getItem('ketchup-multi-server-selections');
    if (storedSelections) {
      try {
        const parsed = JSON.parse(storedSelections);
        if (Array.isArray(parsed)) {
          setSelectedContainers(parsed);
        }
      } catch (err) {
        console.error('Failed to load saved selections:', err);
      }
    }
  }, []);

  // Load sidebar collapsed state from localStorage
  useEffect(() => {
    const storedCollapsed = localStorage.getItem('ketchup-log-viewer-sidebar-collapsed');
    if (storedCollapsed !== null) {
      setSidebarCollapsed(storedCollapsed === 'true');
    }
  }, []);

  // Load layout preference from localStorage
  useEffect(() => {
    const storedLayout = localStorage.getItem('ketchup-log-viewer-layout') as 'merged' | 'stacked' | 'hybrid' | null;
    if (storedLayout) {
      setLayout(storedLayout);
    }
  }, []);

  // Load sidebar width from localStorage
  useEffect(() => {
    const storedWidth = localStorage.getItem('ketchup-log-viewer-sidebar-width');
    if (storedWidth) {
      setSidebarWidth(parseInt(storedWidth));
    }
  }, []);

  // Toggle theme and save to localStorage
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark';
    setTheme(newTheme);
    localStorage.setItem('ketchup-log-viewer-theme', newTheme);
  };

  // Toggle sidebar and save to localStorage
  const toggleSidebar = () => {
    const newCollapsed = !sidebarCollapsed;
    setSidebarCollapsed(newCollapsed);
    localStorage.setItem('ketchup-log-viewer-sidebar-collapsed', newCollapsed.toString());
  };

  // Handle sidebar resize
  const startResizing = (e: React.MouseEvent) => {
    setIsResizing(true);
    e.preventDefault();
  };

  // Mouse move and up handlers for resizing
  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const newWidth = e.clientX;
      const MIN_WIDTH = 200;
      const MAX_WIDTH = 800;

      if (newWidth >= MIN_WIDTH && newWidth <= MAX_WIDTH) {
        setSidebarWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      localStorage.setItem('ketchup-log-viewer-sidebar-width', sidebarWidth.toString());
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, sidebarWidth]);

  // Auto-connect to both servers on mount
  useEffect(() => {
    connectToServer('prod1');
    connectToServer('prod2');
  }, []);

  // Connect to server with async polling for Okta 2FA
  const connectToServer = async (server: 'prod1' | 'prod2') => {
    setIsConnecting(true);
    setError(null);
    setOktaPrompt({ visible: true, server });

    try {
      // Initiate connection (non-blocking)
      const response = await fetch('/api/ssh/connect', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ server }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || 'Connection failed');
      }

      // If already connected, skip polling
      if (data.status === 'connected') {
        setConnectedServers((prev) => new Set(prev).add(server));
        setOktaPrompt({ visible: false, server: '' });
        setIsConnecting(false);
        return;
      }

      // Poll status every 2 seconds with 90-second timeout
      const pollStartTime = Date.now();
      const POLL_INTERVAL = 2000; // 2 seconds
      const POLL_TIMEOUT = 90000; // 90 seconds

      const pollInterval = setInterval(async () => {
        // Check timeout
        if (Date.now() - pollStartTime > POLL_TIMEOUT) {
          clearInterval(pollInterval);
          setError('Connection timeout - Okta approval took too long');
          setOktaPrompt({ visible: false, server: '' });
          setIsConnecting(false);
          return;
        }

        // Poll status
        const statusResponse = await fetch(`/api/ssh/connect/status?server=${server}`);
        const statusData = await statusResponse.json();

        if (statusData.status === 'connected') {
          clearInterval(pollInterval);
          setConnectedServers((prev) => new Set(prev).add(server));
          setOktaPrompt({ visible: false, server: '' });
          setIsConnecting(false);
        } else if (statusData.status === 'failed') {
          clearInterval(pollInterval);
          setError(statusData.error || 'Connection failed');
          setOktaPrompt({ visible: false, server: '' });
          setIsConnecting(false);
        }
      }, POLL_INTERVAL);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      setOktaPrompt({ visible: false, server: '' });
      setIsConnecting(false);
    }
  };

  return (
    <main className={`flex flex-col h-screen ${theme === 'dark' ? 'bg-gray-900 text-white' : 'bg-white text-gray-900'}`}>
      {/* Okta authentication prompt */}
      <OktaAuthPrompt
        server={oktaPrompt.server}
        isVisible={oktaPrompt.visible}
      />

      {/* Header */}
      <header className={`${theme === 'dark' ? 'bg-gray-800 border-gray-700' : 'bg-gray-100 border-gray-300'} border-b p-4`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className={`text-2xl font-bold ${theme === 'dark' ? 'text-white' : 'text-gray-900'}`}>
              🥫 Ketchup Log Viewer
            </h1>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className={`px-3 py-1 text-xs rounded border ${
                theme === 'dark'
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
                  : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
              }`}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            >
              {theme === 'dark' ? '☀️ Light' : '🌙 Dark'}
            </button>

            {/* Layout Selector */}
            <select
              value={layout}
              onChange={(e) => {
                const newLayout = e.target.value as 'merged' | 'stacked' | 'hybrid';
                setLayout(newLayout);
                localStorage.setItem('ketchup-log-viewer-layout', newLayout);
              }}
              className={`px-3 py-1 text-xs rounded border ${
                theme === 'dark'
                  ? 'bg-gray-700 hover:bg-gray-600 text-gray-300 border-gray-600'
                  : 'bg-white hover:bg-gray-50 text-gray-700 border-gray-300'
              }`}
              title="Select layout mode"
            >
              <option value="merged">📊 Merged</option>
              <option value="stacked">📚 Stacked</option>
              <option value="hybrid">🔍 Hybrid</option>
            </select>
          </div>

          {/* Server Connection Status */}
          <div className="flex items-center space-x-4">
            <span className="text-sm text-gray-400">Servers:</span>
            {(['prod1', 'prod2'] as const).map((server) => {
              const isConnected = connectedServers.has(server);

              return (
                <div
                  key={server}
                  className="flex items-center space-x-2 px-3 py-1.5 rounded border"
                  style={{
                    backgroundColor: isConnected
                      ? server === 'prod1'
                        ? 'rgba(37, 99, 235, 0.1)'
                        : 'rgba(34, 197, 94, 0.1)'
                      : theme === 'dark'
                      ? 'rgba(107, 114, 128, 0.1)'
                      : 'rgba(229, 231, 235, 0.5)',
                    borderColor: isConnected
                      ? server === 'prod1'
                        ? 'rgba(37, 99, 235, 0.4)'
                        : 'rgba(34, 197, 94, 0.4)'
                      : theme === 'dark'
                      ? 'rgba(107, 114, 128, 0.3)'
                      : 'rgba(209, 213, 219, 0.5)',
                  }}
                >
                  <span
                    className={`w-2 h-2 rounded-full ${
                      isConnected ? 'bg-green-500' : 'bg-red-500'
                    }`}
                  />
                  <span className={`text-sm font-mono ${
                    isConnected
                      ? theme === 'dark' ? 'text-white' : 'text-gray-900'
                      : 'text-gray-500'
                  }`}>
                    {server}
                  </span>
                  {!isConnected && (
                    <button
                      onClick={() => connectToServer(server)}
                      disabled={isConnecting}
                      className="ml-1 px-2 py-0.5 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded disabled:opacity-50"
                      title={`Connect to ${server}`}
                    >
                      Connect
                    </button>
                  )}
                </div>
              );
            })}
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className={`mt-4 p-3 rounded border ${
            theme === 'dark'
              ? 'bg-red-900 border-red-700 text-red-200'
              : 'bg-red-50 border-red-300 text-red-800'
          }`}>
            {error}
          </div>
        )}
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar - Container selector */}
        <aside
          className={`relative border-r overflow-hidden ${
            sidebarCollapsed ? '' : 'transition-none'
          } ${
            theme === 'dark'
              ? 'bg-gray-800 border-gray-700'
              : 'bg-gray-50 border-gray-200'
          }`}
          style={{
            width: sidebarCollapsed ? '48px' : `${sidebarWidth}px`,
            transition: sidebarCollapsed ? 'width 0.3s ease-in-out' : 'none',
          }}
        >
          {/* Sidebar toggle button */}
          <div className={`${sidebarCollapsed ? 'p-2' : 'p-4 pb-2'} border-b ${
            theme === 'dark' ? 'border-gray-700' : 'border-gray-200'
          }`}>
            <button
              onClick={toggleSidebar}
              className={`${
                sidebarCollapsed ? 'w-full' : 'float-right'
              } p-1 rounded transition-colors ${
                theme === 'dark'
                  ? 'hover:bg-gray-700 text-gray-400'
                  : 'hover:bg-gray-200 text-gray-600'
              }`}
              title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            >
              {sidebarCollapsed ? '▶' : '◀'}
            </button>
            {!sidebarCollapsed && <div className="clear-both" />}
          </div>

          {/* Sidebar content */}
          <div className={`${sidebarCollapsed ? 'hidden' : 'block p-4 overflow-y-auto'} h-[calc(100%-3.5rem)]`}>
            {connectedServers.size > 0 ? (
              <ContainerSelector
                servers={Array.from(connectedServers) as ('prod1' | 'prod2')[]}
                selectedContainers={selectedContainers}
                onSelectionChange={(selections) => {
                  setSelectedContainers(selections);
                  localStorage.setItem('ketchup-multi-server-selections', JSON.stringify(selections));
                }}
                theme={theme}
              />
            ) : (
              <div className={`flex items-center justify-center h-full ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`}>
                <div className="text-center">
                  <p>No servers connected</p>
                  <p className="text-sm mt-2">Waiting for server connections...</p>
                  {isConnecting && (
                    <div className="mt-4 flex items-center justify-center space-x-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                      <span className="text-sm">Connecting...</span>
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Resize Handle */}
          {!sidebarCollapsed && (
            <div
              className={`absolute top-0 right-0 w-1 h-full cursor-ew-resize ${
                isResizing ? 'bg-cyan-500' : theme === 'dark' ? 'bg-gray-700 hover:bg-cyan-500' : 'bg-gray-300 hover:bg-blue-500'
              } transition-colors`}
              onMouseDown={startResizing}
              title="Drag to resize sidebar"
            />
          )}
        </aside>

        {/* Main area - Log viewers */}
        <section className="flex-1 overflow-hidden">
          {selectedContainers.length === 0 ? (
            <div className={`flex items-center justify-center h-full ${theme === 'dark' ? 'text-gray-500' : 'text-gray-400'}`}>
              <div className="text-center">
                <p className="text-lg">No containers selected</p>
                <p className="mt-2 text-sm">
                  Select containers from the sidebar to view logs
                </p>
              </div>
            </div>
          ) : layout === 'stacked' ? (
            <StackedLogViewer
              selections={selectedContainers}
              theme={theme}
            />
          ) : layout === 'hybrid' ? (
            <HybridLogViewer
              selections={selectedContainers}
              theme={theme}
            />
          ) : (
            <MergedLogViewer
              selections={selectedContainers}
              autoScroll={true}
              theme={theme}
            />
          )}
        </section>
      </div>
    </main>
  );
}
