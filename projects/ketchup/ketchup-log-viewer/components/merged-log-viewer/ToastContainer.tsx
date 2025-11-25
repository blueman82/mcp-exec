/**
 * ToastContainer Component
 * Displays toast notifications in the top-right corner with auto-dismiss
 */

'use client';

import React from 'react';
import type { Toast } from '@/hooks/useToastNotifications';

interface ToastContainerProps {
  toasts: Toast[];
  onRemoveToast: (id: number) => void;
}

const ToastContainer: React.FC<ToastContainerProps> = ({ toasts, onRemoveToast }) => {
  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 space-y-2">
      {toasts.map((toast) => {
        const bgColor =
          toast.type === 'success'
            ? 'bg-green-600'
            : toast.type === 'error'
            ? 'bg-red-600'
            : toast.type === 'warning'
            ? 'bg-yellow-600'
            : 'bg-blue-600';

        const icon =
          toast.type === 'success'
            ? '✓'
            : toast.type === 'error'
            ? '✕'
            : toast.type === 'warning'
            ? '⚠'
            : 'ℹ';

        return (
          <div
            key={toast.id}
            className={`${bgColor} text-white px-4 py-3 rounded shadow-lg flex items-center space-x-3 min-w-[250px] max-w-[400px] animate-slide-in-right`}
          >
            <span className="text-lg font-bold">{icon}</span>
            <span className="flex-1">{toast.message}</span>
            <button
              onClick={() => onRemoveToast(toast.id)}
              className="text-white hover:text-gray-200 ml-2"
              aria-label="Close notification"
            >
              ✕
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default ToastContainer;
