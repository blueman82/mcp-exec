/**
 * ErrorDisplay Component
 *
 * Displays error messages with accessibility features
 * and proper ARIA attributes.
 */

import React from 'react';

interface ErrorDisplayProps {
  error: string | null;
  theme: 'dark' | 'light';
}

const ErrorDisplay: React.FC<ErrorDisplayProps> = ({
  error,
  theme
}) => {
  if (!error) {
    return null;
  }

  return (
    <div
      className="mt-3 p-3 rounded-lg bg-red-100 border border-red-300 text-red-700 text-sm flex items-center gap-2"
      role="alert"
      aria-live="assertive"
    >
      <span aria-hidden="true">⚠️</span>
      <span>{error}</span>
    </div>
  );
};

export default ErrorDisplay;