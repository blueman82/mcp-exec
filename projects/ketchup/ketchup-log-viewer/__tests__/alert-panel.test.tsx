import React from 'react';
import { describe, beforeEach, afterEach, it, expect, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import AlertPanel from '@/components/AlertPanel';
import { getAlertManager } from '@/lib/alert-manager';

const localStorageMock = (() => {
  let store: Record<string, string> = {};

  return {
    getItem: vi.fn((key: string) => store[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      store[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete store[key];
    }),
    clear: vi.fn(() => {
      store = {};
    }),
  };
})();

describe('AlertPanel', () => {
  beforeEach(() => {
    Object.defineProperty(window, 'localStorage', {
      value: localStorageMock,
      configurable: true,
    });
    localStorageMock.clear();
    const manager = getAlertManager();
    manager.reset();
    manager.destroy();
  });

  afterEach(() => {
    const manager = getAlertManager();
    manager.reset();
    manager.destroy();
  });

  it('allows creating a new alert pattern through the form', async () => {
    await act(async () => {
      render(<AlertPanel theme="dark" containers={['ketchup-app']} servers={['prod1', 'prod2']} />);
    });

    const nameInput = screen.getByPlaceholderText('e.g. Critical errors in metadata service');
    const patternInput = screen.getByPlaceholderText('e.g. (error|fatal|panic)');

    await act(async () => {
      fireEvent.change(nameInput, { target: { value: 'Metadata errors' } });
      fireEvent.change(patternInput, { target: { value: 'metadata error' } });
      fireEvent.click(screen.getByText('Create Alert'));
    });

    await waitFor(() => {
      expect(screen.getByText('Metadata errors')).toBeInTheDocument();
    });

    const manager = getAlertManager();
    const state = manager.getState();
    expect(state.patterns.some((pattern) => pattern.name === 'Metadata errors')).toBe(true);
  });

  it('shows active alerts and supports acknowledging them', async () => {
    const manager = getAlertManager();
    const pattern = manager.addPattern({
      name: 'Timeout detector',
      expression: 'timeout',
      description: '',
      severity: 'high',
      cooldownMinutes: 0,
      containers: [],
      servers: [],
      actions: [{ type: 'toast' }],
      flags: 'gi',
      enabled: true,
    });

    manager.processLogLine({
      timestamp: new Date().toISOString(),
      content: 'Request timeout in ketchup-app',
      container: 'ketchup-app',
      server: 'prod1',
      level: 'error',
    });

    await act(async () => {
      render(<AlertPanel theme="dark" containers={['ketchup-app']} servers={['prod1']} />);
    });

    await waitFor(() => {
      expect(screen.getAllByText(pattern.name).length).toBeGreaterThan(0);
      expect(screen.getByText(/active alerts/i)).toBeInTheDocument();
      expect(screen.getAllByText(/Request timeout in ketchup-app/).length).toBeGreaterThan(0);
    });

    const activeAlertsSection = screen.getByLabelText('Active alerts');
    const acknowledgeButton = within(activeAlertsSection).getByRole('button', { name: /^Acknowledge$/i });
    await act(async () => {
      fireEvent.click(acknowledgeButton);
    });

    await waitFor(() => {
      const state = getAlertManager().getState();
      expect(state.activeAlerts).toHaveLength(0);
      expect(state.alertHistory[0].acknowledged).toBe(true);
    });
  });
});
