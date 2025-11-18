/**
 * Custom hook for managing accessibility features
 * Handles screen reader announcements and live region updates
 */

import { useCallback, useRef, useState } from 'react';

export interface UseAccessibilityReturn {
  announcementMessage: string;
  announcementLiveRef: React.RefObject<HTMLDivElement>;
  announceToScreenReader: (message: string, priority?: 'polite' | 'assertive') => void;
}

export function useAccessibility(): UseAccessibilityReturn {
  const [announcementMessage, setAnnouncementMessage] = useState<string>('');
  const announcementLiveRef = useRef<HTMLDivElement>(null);

  const announceToScreenReader = useCallback(
    (message: string, priority: 'polite' | 'assertive' = 'polite') => {
      setAnnouncementMessage(message);
      if (announcementLiveRef.current) {
        announcementLiveRef.current.textContent = message;
        announcementLiveRef.current.setAttribute('aria-live', priority);
        // Clear after announcement
        setTimeout(() => {
          if (announcementLiveRef.current) {
            announcementLiveRef.current.textContent = '';
          }
        }, 1000);
      }
    },
    []
  );

  return {
    announcementMessage,
    announcementLiveRef,
    announceToScreenReader,
  };
}
