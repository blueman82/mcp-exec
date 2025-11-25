/**
 * FilterPill Component
 *
 * Interactive filter pill component for filtering search results.
 * Supports keyboard navigation and accessibility features.
 */

import React from 'react';

interface FilterPillProps {
  label: string;
  value: string;
  isActive: boolean;
  onClick: () => void;
  onRemove?: () => void;
  color?: string;
  theme: 'dark' | 'light';
  size?: 'sm' | 'md' | 'lg';
}

const FilterPill: React.FC<FilterPillProps> = ({
  label,
  value,
  isActive,
  onClick,
  onRemove,
  color = 'blue',
  theme
}) => {
  const baseClasses = 'inline-flex items-center px-3 py-1 rounded-full text-sm font-medium transition-all duration-200 cursor-pointer border focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-opacity-50';
  const activeClasses = theme === 'dark'
    ? `bg-${color}-600 text-white border-${color}-500`
    : `bg-${color}-500 text-white border-${color}-400`;
  const inactiveClasses = theme === 'dark'
    ? 'bg-gray-700 text-gray-300 border-gray-600 hover:bg-gray-600'
    : 'bg-gray-200 text-gray-700 border-gray-300 hover:bg-gray-300';

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  const handleRemoveClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (onRemove) {
      onRemove();
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-label={`Filter by ${label}: ${value}`}
      aria-pressed={isActive}
      className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}
      onClick={onClick}
      onKeyDown={handleKeyDown}
    >
      <span>{label}: {value}</span>
      {onRemove && (
        <button
          onClick={handleRemoveClick}
          aria-label={`Remove ${label} filter: ${value}`}
          className="ml-2 hover:opacity-70 focus:outline-none focus:ring-1 focus:ring-white focus:ring-opacity-50"
        >
          ✕
        </button>
      )}
    </div>
  );
};

export default FilterPill;