/**
 * Custom hook for managing resizable panel layout
 * Supports mouse and keyboard-based resizing with accessibility features
 */

import { useState, useCallback, useEffect, useRef } from 'react';

export interface PanelDimensions {
  leftWidth: number;
  rightWidth: number;
}

export interface UsePanelResizeReturn {
  panelDimensions: PanelDimensions;
  isResizing: boolean;
  panelResizeValue: number;
  resizeHandleRef: React.RefObject<HTMLDivElement>;
  handleResizeStart: (e: React.MouseEvent) => void;
  handleResizeKeyDown: (e: React.KeyboardEvent) => void;
}

export interface UsePanelResizeOptions {
  initialLeftWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  onResize?: (dimensions: PanelDimensions) => void;
  onResizeComplete?: (dimensions: PanelDimensions) => void;
}

export function usePanelResize(options: UsePanelResizeOptions = {}): UsePanelResizeReturn {
  const {
    initialLeftWidth = 30,
    minWidth = 20,
    maxWidth = 80,
    onResize,
    onResizeComplete,
  } = options;

  const [panelDimensions, setPanelDimensions] = useState<PanelDimensions>({
    leftWidth: initialLeftWidth,
    rightWidth: 100 - initialLeftWidth,
  });
  const [isResizing, setIsResizing] = useState(false);
  const [panelResizeValue, setPanelResizeValue] = useState(initialLeftWidth);
  const resizeHandleRef = useRef<HTMLDivElement>(null);

  const updateDimensions = useCallback(
    (newLeftWidth: number) => {
      const clampedLeftWidth = Math.max(minWidth, Math.min(maxWidth, newLeftWidth));
      const newDimensions = {
        leftWidth: clampedLeftWidth,
        rightWidth: 100 - clampedLeftWidth,
      };
      setPanelResizeValue(clampedLeftWidth);
      setPanelDimensions(newDimensions);
      onResize?.(newDimensions);
      return newDimensions;
    },
    [minWidth, maxWidth, onResize]
  );

  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
    resizeHandleRef.current?.focus();
  }, []);

  const handleResizeKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const step = 5; // 5% increments
      let newValue = panelResizeValue;

      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault();
          newValue = panelResizeValue - step;
          break;
        case 'ArrowRight':
          e.preventDefault();
          newValue = panelResizeValue + step;
          break;
        case 'Home':
          e.preventDefault();
          newValue = minWidth;
          break;
        case 'End':
          e.preventDefault();
          newValue = maxWidth;
          break;
        case 'Enter':
        case ' ':
          e.preventDefault();
          setIsResizing(false);
          onResizeComplete?.(panelDimensions);
          return;
        case 'Escape':
          e.preventDefault();
          setIsResizing(false);
          return;
        default:
          return;
      }

      updateDimensions(newValue);
    },
    [panelResizeValue, minWidth, maxWidth, panelDimensions, updateDimensions, onResizeComplete]
  );

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const containerWidth = window.innerWidth;
      const newLeftWidth = (e.clientX / containerWidth) * 100;
      updateDimensions(newLeftWidth);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      onResizeComplete?.(panelDimensions);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, panelDimensions, updateDimensions, onResizeComplete]);

  return {
    panelDimensions,
    isResizing,
    panelResizeValue,
    resizeHandleRef,
    handleResizeStart,
    handleResizeKeyDown,
  };
}
