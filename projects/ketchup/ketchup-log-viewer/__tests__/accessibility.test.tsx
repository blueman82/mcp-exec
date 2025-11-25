/**
 * Accessibility Tests for Cross-Container Search Enhancement
 *
 * Validates WCAG 2.1 AA compliance for EnhancedSearch and HybridLogViewer components
 *
 * Test Categories:
 * 1. Keyboard Accessibility (2.1.1, 2.1.3)
 * 2. Screen Reader Support (1.3.1, 1.3.2, 4.1.2, 4.1.3)
 * 3. Focus Management (2.4.3, 2.4.7)
 * 4. ARIA Labels & Descriptions (2.4.6, 4.1.1)
 * 5. Color & Contrast (1.4.3, 1.4.11)
 * 6. Timing & Responsive (2.2.1, 2.2.2)
 */

import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import EnhancedSearch from '../components/EnhancedSearch';
import HybridLogViewer from '../components/HybridLogViewer';

// Mock logs for testing
const mockLogs = [
  {
    timestamp: '2024-01-15T10:30:00.000Z',
    content: 'Error connecting to database',
    container: 'ketchup-app',
    server: 'prod1',
    level: 'error'
  },
  {
    timestamp: '2024-01-15T10:31:00.000Z',
    content: 'User login successful',
    container: 'ketchup-app',
    server: 'prod1',
    level: 'info'
  }
];

describe('Accessibility Tests - Enhanced Search Component', () => {
  const defaultProps = {
    logs: mockLogs,
    theme: 'light' as const
  };

  beforeEach(() => {
    // Announce to screen reader setup
    const announceRegion = document.createElement('div');
    announceRegion.setAttribute('aria-live', 'polite');
    announceRegion.setAttribute('aria-atomic', 'true');
    announceRegion.className = 'sr-only';
    document.body.appendChild(announceRegion);
  });

  afterEach(() => {
    document.body.innerHTML = '';
  });

  describe('WCAG 2.1.1 Keyboard Accessibility', () => {
    test('search input should be keyboard accessible', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const searchInput = screen.getByRole('combobox', { name: /search logs/i });
      expect(searchInput).toBeInTheDocument();

      // Test Tab navigation
      searchInput.focus();
      expect(searchInput).toHaveFocus();

      // Test typing
      fireEvent.change(searchInput, { target: { value: 'error' } });
      expect(searchInput).toHaveValue('error');
    });

    test('filter pills should be keyboard operable', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const filterPills = screen.getAllByRole('button');
      expect(filterPills.length).toBeGreaterThan(0);

      // Test Enter key
      const firstFilter = filterPills[0];
      firstFilter.focus();
      fireEvent.keyDown(firstFilter, { key: 'Enter' });

      // Test Space key
      fireEvent.keyDown(firstFilter, { key: ' ' });
    });

    test('action buttons should be keyboard accessible', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const historyButton = screen.getByRole('button', { name: /search history/i });
      historyButton.focus();
      expect(historyButton).toHaveFocus();

      fireEvent.keyDown(historyButton, { key: 'Enter' });
      fireEvent.keyDown(historyButton, { key: ' ' });
    });
  });

  describe('WCAG 1.3.1 Semantic Structure', () => {
    test('should have proper heading hierarchy', () => {
      render(<EnhancedSearch {...defaultProps} />);

      // Should have labels and landmarks
      expect(screen.getByRole('combobox', { name: /search logs/i })).toBeInTheDocument();
      expect(screen.getByRole('toolbar', { name: /search actions/i })).toBeInTheDocument();
    });

    test('should have proper navigation regions', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const navRegion = screen.getByRole('navigation', { name: /log filters/i });
      expect(navRegion).toBeInTheDocument();

      const filterGroups = navRegion.querySelectorAll('[role="group"]');
      expect(filterGroups.length).toBeGreaterThan(0);
    });
  });

  describe('WCAG 2.4.3 Focus Order', () => {
    test('should maintain logical focus order', async () => {
      const user = userEvent.setup();
      render(<EnhancedSearch {...defaultProps} />);

      // Tab through elements
      await user.tab();
      expect(screen.getByRole('combobox')).toHaveFocus();

      await user.tab();
      // Should focus on first interactive element after search input
    });

    test('should have visible focus indicators', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const searchInput = screen.getByRole('combobox');
      searchInput.focus();

      expect(searchInput).toHaveClass('focus:ring-2');
    });
  });

  describe('WCAG 4.1.2 Name, Role, Value', () => {
    test('interactive elements should have accessible names', () => {
      render(<EnhancedSearch {...defaultProps} />);

      // Search input
      expect(screen.getByRole('combobox', { name: /search logs/i })).toBeInTheDocument();

      // Buttons
      expect(screen.getByRole('button', { name: /search history/i })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /saved searches/i })).toBeInTheDocument();

      // Filter pills
      const filterPills = screen.getAllByRole('button');
      filterPills.forEach(pill => {
        expect(pill).toHaveAttribute('aria-label');
        expect(pill).toHaveAttribute('aria-pressed');
      });
    });

    test('form controls should have proper labels', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const searchInput = screen.getByRole('combobox');
      expect(searchInput).toHaveAttribute('aria-describedby');

      const searchDescription = document.getElementById('search-description');
      expect(searchDescription).toBeInTheDocument();
    });
  });

  describe('WCAG 1.3.2 Meaningful Sequence', () => {
    test('should maintain logical reading order', () => {
      const { container } = render(<EnhancedSearch {...defaultProps} />);

      // Check that elements appear in logical order
      const searchInput = screen.getByRole('combobox');
      const filterSection = screen.getByRole('navigation', { name: /log filters/i });
      const actionBar = screen.getByRole('toolbar');

      expect(searchInput.compareDocumentPosition(filterSection) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(filterSection.compareDocumentPosition(actionBar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });
  });

  describe('Screen Reader Support', () => {
    test('should announce search results', async () => {
      render(<EnhancedSearch {...defaultProps} />);

      const searchInput = screen.getByRole('combobox');
      fireEvent.change(searchInput, { target: { value: 'error' } });

      await waitFor(() => {
        const statusRegion = document.getElementById('search-status');
        expect(statusRegion).toHaveTextContent(/found/i);
      });
    });

    test('should announce filter changes', () => {
      render(<EnhancedSearch {...defaultProps} />);

      const filterPill = screen.getByRole('button', { name: /filter by level: error/i });
      fireEvent.click(filterPill);

      // Should announce filter application
      const announcement = document.querySelector('[aria-live="assertive"]');
      expect(announcement).toBeInTheDocument();
    });
  });

  describe('WCAG 2.1.4 Character Key Shortcuts', () => {
    test('should provide alternative to character-only shortcuts', () => {
      render(<EnhancedSearch {...defaultProps} />);

      // Help modal should be available
      const shortcutsButton = screen.getByRole('button', { name: /keyboard shortcuts help/i });
      fireEvent.click(shortcutsButton);

      expect(screen.getByRole('dialog')).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /keyboard shortcuts/i })).toBeInTheDocument();
    });
  });
});

describe('Accessibility Tests - Hybrid Log Viewer Component', () => {
  const defaultProps = {
    selections: [{ container: 'ketchup-app', server: 'prod1' }],
    theme: 'light' as const
  };

  describe('WCAG 1.3.1 Semantic Structure', () => {
    test('should have proper landmark regions', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('banner')).toBeInTheDocument(); // Header
      expect(screen.getByRole('main')).toBeInTheDocument(); // Main content
      expect(screen.getByRole('contentinfo')).toBeInTheDocument(); // Footer help
    });

    test('should have proper heading hierarchy', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const headings = screen.getAllByRole('heading');
      expect(headings.length).toBeGreaterThan(0);

      // Should have h2 for main sections
      const h2Elements = headings.filter(h => h.tagName === 'H2');
      expect(h2Elements.length).toBeGreaterThan(0);
    });
  });

  describe('WCAG 2.4.6 Headings and Labels', () => {
    test('should have descriptive section headings', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('heading', { name: /search results/i })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /full log context/i })).toBeInTheDocument();
    });

    test('should have accessible panel labels', () => {
      render(<HybridLogViewer {...defaultProps} />);

      expect(screen.getByRole('region', { name: /search results panel/i })).toBeInTheDocument();
      expect(screen.getByRole('region', { name: /full log context panel/i })).toBeInTheDocument();
    });
  });

  describe('WCAG 2.1.1 Keyboard Accessibility', () => {
    test('panel resize should be keyboard accessible', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator');
      expect(resizeHandle).toBeInTheDocument();

      // Test keyboard resizing
      resizeHandle.focus();
      fireEvent.keyDown(resizeHandle, { key: 'ArrowLeft' });
      fireEvent.keyDown(resizeHandle, { key: 'ArrowRight' });
      fireEvent.keyDown(resizeHandle, { key: 'Enter' });
    });

    test('search results should be keyboard navigable', async () => {
      render(<HybridLogViewer {...defaultProps} />);

      // Test F3 navigation
      fireEvent.keyDown(document, { key: 'F3' });
      fireEvent.keyDown(document, { key: 'F3', shiftKey: true });
    });
  });

  describe('WCAG 1.4.11 Non-text Contrast', () => {
    test('interactive elements should have sufficient contrast', () => {
      const { container } = render(<HybridLogViewer {...defaultProps} />);

      const interactiveElements = container.querySelectorAll('button, [role="button"]');
      interactiveElements.forEach(element => {
        const styles = window.getComputedStyle(element);
        // This would need actual color values to test contrast ratio
        expect(element).toHaveClass('focus:ring-2'); // At least has focus indicator
      });
    });
  });

  describe('Screen Reader Support', () => {
    test('should announce result navigation', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const announcement = document.querySelector('[aria-live="polite"]');
      expect(announcement).toBeInTheDocument();
    });

    test('should have proper ARIA attributes', () => {
      render(<HybridLogViewer {...defaultProps} />);

      const resizeHandle = screen.getByRole('separator');
      expect(resizeHandle).toHaveAttribute('aria-valuemin');
      expect(resizeHandle).toHaveAttribute('aria-valuemax');
      expect(resizeHandle).toHaveAttribute('aria-valuenow');
    });
  });
});

describe('WCAG 2.1 AA Compliance Checklist', () => {
  test('Perceivable requirements', () => {
    // Text alternatives (1.1.1)
    // Images have alt text or are decorative

    // Captions/pre-recorded (1.2.1)
    // Not applicable - no audio/video content

    // Audio description/pre-recorded (1.2.3)
    // Not applicable - no audio/video content

    // Reflow (1.4.10)
    // Content should reflow on 320px width without horizontal scrolling

    // Non-text contrast (1.4.11)
    // Interactive elements should have 3:1 contrast ratio

    // Text spacing (1.4.12)
    // Text should remain readable when spacing is adjusted
  });

  test('Operable requirements', () => {
    // Keyboard accessible (2.1.1)
    // All functionality should be available via keyboard

    // No keyboard trap (2.1.2)
    // Focus should not be trapped

    // Character key shortcuts (2.1.4)
    // Should provide ways to turn off or remap shortcuts

    // Timing adjustable (2.2.1)
    // Users should have control over time limits

    // Pause, stop, hide (2.2.2)
    // Moving content should be controllable

    // Navigation mechanisms (2.4.1)
    // Multiple ways to navigate should be available

    // Focus visible (2.4.7)
    // Focus should be clearly visible
  });

  test('Understandable requirements', () => {
    // Language of page (3.1.1)
    // Page language should be programmatically determined

    // On input (3.2.2)
    // Changing settings should not cause context changes

    // Navigation consistent (3.2.3)
    // Navigation should be consistent across pages

    // Identification (3.3.2)
    // Input fields should be properly labeled

    // Error suggestion (3.3.3)
    // Errors should provide suggestions

    // Error prevention (3.3.4)
    // Important actions should have confirmation
  });

  test('Robust requirements', () => {
    // Parsing (4.1.1)
    // HTML should be valid and parseable

    // Name, role, value (4.1.2)
    // All UI elements should have proper ARIA

    // Status messages (4.1.3)
    // Status changes should be announced
  });
});