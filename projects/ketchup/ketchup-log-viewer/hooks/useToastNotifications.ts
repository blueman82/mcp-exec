/**
 * Custom hook for managing toast notifications
 * Provides add/remove functionality with auto-dismissal
 */

import { useState, useRef, useCallback } from 'react';

export interface Toast {
  id: number;
  message: string;
  type: 'success' | 'error' | 'info' | 'warning';
}

export interface UseToastNotificationsReturn {
  toasts: Toast[];
  showToast: (message: string, type: Toast['type']) => void;
  removeToast: (id: number) => void;
}

export interface UseToastNotificationsOptions {
  duration?: number;
}

export function useToastNotifications(
  options: UseToastNotificationsOptions = {}
): UseToastNotificationsReturn {
  const { duration = 3000 } = options;
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastIdRef = useRef(0);

  const showToast = useCallback(
    (message: string, type: Toast['type']) => {
      const id = toastIdRef.current++;
      setToasts((prev) => [...prev, { id, message, type }]);

      setTimeout(() => {
        setToasts((prev) => prev.filter((toast) => toast.id !== id));
      }, duration);
    },
    [duration]
  );

  const removeToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  return {
    toasts,
    showToast,
    removeToast,
  };
}
