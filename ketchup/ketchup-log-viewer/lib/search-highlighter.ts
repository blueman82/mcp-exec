/**
 * Search Highlighter - Advanced text highlighting with multiple match types and context
 *
 * Features:
 * - Multiple highlight colors for different match types
 * - Context-aware highlighting with surrounding words
 * - Animated highlights for new matches
 * - Highlight persistence across scroll/resize
 * - Keyboard navigation support (F3, Shift+F3)
 * - Performance optimized for large datasets
 */

import type { SearchMatch, SearchResult } from '@/types/search';
import type { LogLine } from '@/types';

/**
 * Highlight types with associated styling
 */
export type HighlightType = 'primary' | 'secondary' | 'tertiary' | 'context' | 'selected';

/**
 * Highlight configuration
 */
export interface HighlightConfig {
  /** Type of highlight */
  type: HighlightType;
  /** Start position in text */
  start: number;
  /** End position in text */
  end: number;
  /** Text content */
  text: string;
  /** CSS classes for styling */
  className: string;
  /** Unique identifier for this highlight */
  id: string;
  /** Whether this highlight should be animated */
  animated?: boolean;
  /** Additional metadata */
  metadata?: {
    matchIndex?: number;
    score?: number;
    contextLevel?: number;
  };
}

/**
 * Navigation state for highlights
 */
export interface HighlightNavigation {
  /** Total number of highlights */
  total: number;
  /** Currently selected highlight index */
  current: number;
  /** List of highlight IDs in navigation order */
  highlightIds: string[];
}

/**
 * Highlighter options
 */
export interface SearchHighlighterOptions {
  /** Theme (light/dark) */
  theme: 'light' | 'dark';
  /** Whether to enable animations */
  enableAnimations?: boolean;
  /** Context radius in characters */
  contextRadius?: number;
  /** Maximum number of highlights to prevent performance issues */
  maxHighlights?: number;
  /** Custom CSS class overrides */
  customClasses?: Partial<Record<HighlightType, string>>;
}

/**
 * Default highlight color schemes
 */
const DEFAULT_HIGHLIGHT_CLASSES: Record<HighlightType, { light: string; dark: string }> = {
  primary: {
    light: 'bg-yellow-400 text-black',
    dark: 'bg-yellow-500 text-black',
  },
  secondary: {
    light: 'bg-orange-400 text-white',
    dark: 'bg-orange-500 text-white',
  },
  tertiary: {
    light: 'bg-green-400 text-white',
    dark: 'bg-green-500 text-white',
  },
  context: {
    light: 'bg-blue-200 text-black',
    dark: 'bg-blue-800 text-white',
  },
  selected: {
    light: 'bg-purple-500 text-white ring-2 ring-purple-300',
    dark: 'bg-purple-600 text-white ring-2 ring-purple-400',
  },
};

/**
 * Search Highlighter Class
 */
export class SearchHighlighter {
  private options: Required<SearchHighlighterOptions>;
  private highlights: Map<string, HighlightConfig> = new Map();
  private navigation: HighlightNavigation = { total: 0, current: 0, highlightIds: [] };
  private observer: MutationObserver | null = null;
  private container: HTMLElement | null = null;
  private animationTimeouts: Map<string, NodeJS.Timeout> = new Map();

  constructor(options: SearchHighlighterOptions) {
    this.options = {
      enableAnimations: options.enableAnimations ?? true,
      contextRadius: options.contextRadius ?? 50,
      maxHighlights: options.maxHighlights ?? 10000,
      customClasses: options.customClasses ?? {},
      theme: options.theme,
    };
  }

  /**
   * Get CSS classes for a highlight type
   */
  private getHighlightClasses(type: HighlightType): string {
    const customClass = this.options.customClasses[type];
    if (customClass) {
      return customClass;
    }

    const defaultClasses = DEFAULT_HIGHLIGHT_CLASSES[type];
    const themeClasses = this.options.theme === 'dark' ? defaultClasses.dark : defaultClasses.light;

    // Add base classes for all highlights
    const baseClasses = 'px-1 rounded transition-all duration-200';
    const animationClass = this.options.enableAnimations ? 'animate-pulse' : '';

    return `${baseClasses} ${themeClasses} ${animationClass}`.trim();
  }

  /**
   * Generate unique highlight ID
   */
  private generateHighlightId(): string {
    return `highlight-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
  }

  /**
   * Clear all animation timeouts
   */
  private clearAnimationTimeouts(): void {
    for (const timeout of this.animationTimeouts.values()) {
      clearTimeout(timeout);
    }
    this.animationTimeouts.clear();
  }

  /**
   * Create highlight configuration
   */
  private createHighlight(
    type: HighlightType,
    start: number,
    end: number,
    text: string,
    metadata?: HighlightConfig['metadata']
  ): HighlightConfig {
    const id = this.generateHighlightId();

    return {
      type,
      start,
      end,
      text,
      className: this.getHighlightClasses(type),
      id,
      animated: this.options.enableAnimations && type !== 'context',
      metadata,
    };
  }

  /**
   * Extract context around a match
   */
  private extractContext(
    content: string,
    matchStart: number,
    matchEnd: number,
    contextLevel: number = 1
  ): Array<{ start: number; end: number; level: number }> {
    const contexts: Array<{ start: number; end: number; level: number }> = [];
    const radius = this.options.contextRadius;

    // Extract surrounding words as context
    const beforeStart = Math.max(0, matchStart - radius);
    const afterEnd = Math.min(content.length, matchEnd + radius);

    // Find word boundaries for better context
    const beforeText = content.substring(beforeStart, matchStart);
    const afterText = content.substring(matchEnd, afterEnd);

    // Add context before match
    if (beforeText.trim()) {
      const words = beforeText.split(/\s+/);
      let contextStart = matchStart;

      // Include up to contextLevel words before the match
      for (let i = Math.max(0, words.length - contextLevel); i < words.length; i++) {
        const wordIndex = beforeText.lastIndexOf(words[i]);
        if (wordIndex !== -1) {
          contextStart = beforeStart + wordIndex;
        }
      }

      if (contextStart < matchStart) {
        contexts.push({ start: contextStart, end: matchStart, level: contextLevel });
      }
    }

    // Add context after match
    if (afterText.trim()) {
      const words = afterText.split(/\s+/);
      let contextEnd = matchEnd;

      // Include up to contextLevel words after the match
      for (let i = 0; i < Math.min(contextLevel, words.length); i++) {
        const wordIndex = afterText.indexOf(words[i]);
        if (wordIndex !== -1) {
          contextEnd = matchEnd + wordIndex + words[i].length;
        }
      }

      if (contextEnd > matchEnd) {
        contexts.push({ start: matchEnd, end: contextEnd, level: contextLevel });
      }
    }

    return contexts;
  }

  /**
   * Process search results into highlights
   */
  public processSearchResults(searchResult: SearchResult): HighlightConfig[] {
    const highlights: HighlightConfig[] = [];
    let highlightCount = 0;

    for (let i = 0; i < searchResult.matches.length; i++) {
      if (highlightCount >= this.options.maxHighlights) {
        console.warn(`Reached maximum highlight limit (${this.options.maxHighlights})`);
        break;
      }

      const match = searchResult.matches[i];
      const content = match.log.content;

      // Primary highlight for exact match
      if (match.matchStart >= 0 && match.matchEnd > match.matchStart) {
        const primaryHighlight = this.createHighlight(
          'primary',
          match.matchStart,
          match.matchEnd,
          content.substring(match.matchStart, match.matchEnd),
          {
            matchIndex: i,
            score: match.score,
          }
        );
        highlights.push(primaryHighlight);
        highlightCount++;

        // Add context highlights
        const contexts = this.extractContext(
          content,
          match.matchStart,
          match.matchEnd,
          1 // Context level
        );

        for (const context of contexts) {
          if (highlightCount >= this.options.maxHighlights) break;

          const contextHighlight = this.createHighlight(
            'context',
            context.start,
            context.end,
            content.substring(context.start, context.end),
            {
              contextLevel: context.level,
            }
          );
          highlights.push(contextHighlight);
          highlightCount++;
        }
      }
    }

    // Sort highlights by start position
    highlights.sort((a, b) => a.start - b.start);

    // Update internal state
    this.highlights.clear();
    highlights.forEach(highlight => {
      this.highlights.set(highlight.id, highlight);
    });

    // Update navigation
    this.navigation = {
      total: highlights.filter(h => h.type === 'primary').length,
      current: 0,
      highlightIds: highlights.filter(h => h.type === 'primary').map(h => h.id),
    };

    return highlights;
  }

  /**
   * Apply highlights to DOM elements
   */
  public applyHighlights(container: HTMLElement): void {
    this.container = container;
    this.clearHighlights();

    if (this.highlights.size === 0) return;

    // Find all text nodes in the container
    const walker = document.createTreeWalker(
      container,
      NodeFilter.SHOW_TEXT
    );

    const textNodes: Text[] = [];
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent && node.textContent.trim()) {
        textNodes.push(node as Text);
      }
    }

    // Apply highlights to text nodes
    for (const textNode of textNodes) {
      this.highlightTextNode(textNode);
    }

    // Set up mutation observer to maintain highlights
    this.setupMutationObserver();

    // Set up keyboard navigation
    this.setupKeyboardNavigation();
  }

  /**
   * Highlight a single text node
   */
  private highlightTextNode(textNode: Text): void {
    const text = textNode.textContent || '';
    const highlightsInRange = Array.from(this.highlights.values())
      .filter(highlight => {
        // This is a simplified check - in practice, you'd need to track
        // which highlights belong to which text nodes
        return highlight.start < text.length && highlight.end > 0;
      })
      .sort((a, b) => a.start - b.start);

    if (highlightsInRange.length === 0) return;

    const fragment = document.createDocumentFragment();
    let lastIndex = 0;

    for (const highlight of highlightsInRange) {
      // Add text before highlight
      if (highlight.start > lastIndex) {
        fragment.appendChild(document.createTextNode(text.substring(lastIndex, highlight.start)));
      }

      // Create highlighted span
      const span = document.createElement('span');
      span.className = highlight.className;
      span.setAttribute('data-highlight-id', highlight.id);
      span.textContent = highlight.text;

      if (highlight.animated) {
        span.classList.add('highlight-new');

        // Remove animation class after animation completes
        const timeout = setTimeout(() => {
          span.classList.remove('highlight-new');
        }, 1000);

        this.animationTimeouts.set(highlight.id, timeout);
      }

      fragment.appendChild(span);
      lastIndex = highlight.end;
    }

    // Add remaining text
    if (lastIndex < text.length) {
      fragment.appendChild(document.createTextNode(text.substring(lastIndex)));
    }

    // Replace text node with highlighted content
    if (fragment.childNodes.length > 0) {
      textNode.parentNode?.replaceChild(fragment, textNode);
    }
  }

  /**
   * Clear all highlights from the container
   */
  public clearHighlights(): void {
    if (!this.container) return;

    this.clearAnimationTimeouts();

    // Remove highlighted spans
    const highlightedElements = this.container.querySelectorAll('[data-highlight-id]');
    highlightedElements.forEach(element => {
      const parent = element.parentNode;
      if (parent) {
        // Replace with text content
        parent.replaceChild(document.createTextNode(element.textContent || ''), element);

        // Normalize adjacent text nodes
        parent.normalize();
      }
    });

    // Disconnect mutation observer
    if (this.observer) {
      this.observer.disconnect();
      this.observer = null;
    }
  }

  /**
   * Set up mutation observer to maintain highlights
   */
  private setupMutationObserver(): void {
    if (!this.container || this.observer) return;

    this.observer = new MutationObserver((mutations) => {
      let shouldReapply = false;

      for (const mutation of mutations) {
        if (mutation.type === 'childList' || mutation.type === 'characterData') {
          shouldReapply = true;
          break;
        }
      }

      if (shouldReapply) {
        // Debounce reapplication
        setTimeout(() => {
          if (this.container) {
            this.applyHighlights(this.container);
          }
        }, 100);
      }
    });

    this.observer.observe(this.container, {
      childList: true,
      subtree: true,
      characterData: true,
    });
  }

  /**
   * Set up keyboard navigation
   */
  private setupKeyboardNavigation(): void {
    const handleKeyDown = (e: KeyboardEvent) => {
      // F3: Next highlight
      if (e.key === 'F3' && !e.shiftKey) {
        e.preventDefault();
        this.navigateToNext();
      }

      // Shift+F3: Previous highlight
      if (e.key === 'F3' && e.shiftKey) {
        e.preventDefault();
        this.navigateToPrevious();
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    // Store reference for cleanup
    (this as any)._keyDownHandler = handleKeyDown;
  }

  /**
   * Navigate to next highlight
   */
  public navigateToNext(): void {
    if (this.navigation.total === 0) return;

    this.navigation.current = (this.navigation.current + 1) % this.navigation.total;
    this.updateHighlightSelection();
  }

  /**
   * Navigate to previous highlight
   */
  public navigateToPrevious(): void {
    if (this.navigation.total === 0) return;

    this.navigation.current = this.navigation.current === 0
      ? this.navigation.total - 1
      : this.navigation.current - 1;
    this.updateHighlightSelection();
  }

  /**
   * Navigate to specific highlight by index
   */
  public navigateToHighlight(index: number): void {
    if (index < 0 || index >= this.navigation.total) return;

    this.navigation.current = index;
    this.updateHighlightSelection();
  }

  /**
   * Update highlight selection styling
   */
  private updateHighlightSelection(): void {
    if (!this.container) return;

    // Remove previous selection styling
    const previousSelected = this.container.querySelectorAll('[data-highlight-selected]');
    previousSelected.forEach(element => {
      element.removeAttribute('data-highlight-selected');
      const highlightId = element.getAttribute('data-highlight-id');
      if (highlightId) {
        const highlight = this.highlights.get(highlightId);
        if (highlight) {
          element.className = highlight.className;
        }
      }
    });

    // Add selection styling to current highlight
    const currentHighlightId = this.navigation.highlightIds[this.navigation.current];
    if (currentHighlightId) {
      const currentElement = this.container.querySelector(`[data-highlight-id="${currentHighlightId}"]`);
      if (currentElement) {
        currentElement.setAttribute('data-highlight-selected', 'true');
        const selectedHighlight = this.highlights.get(currentHighlightId);
        if (selectedHighlight) {
          const selectedClasses = this.getHighlightClasses('selected');
          currentElement.className = `${selectedHighlight.className} ${selectedClasses}`.trim();
        }

        // Scroll into view
        currentElement.scrollIntoView({
          behavior: 'smooth',
          block: 'center',
          inline: 'nearest',
        });
      }
    }
  }

  /**
   * Get current navigation state
   */
  public getNavigationState(): HighlightNavigation {
    return { ...this.navigation };
  }

  /**
   * Get all highlights
   */
  public getHighlights(): HighlightConfig[] {
    return Array.from(this.highlights.values());
  }

  /**
   * Update theme
   */
  public updateTheme(theme: 'light' | 'dark'): void {
    this.options.theme = theme;

    // Update highlight classes
    for (const highlight of this.highlights.values()) {
      highlight.className = this.getHighlightClasses(highlight.type);
    }

    // Reapply highlights if container exists
    if (this.container) {
      this.applyHighlights(this.container);
    }
  }

  /**
   * Destroy highlighter and clean up resources
   */
  public destroy(): void {
    this.clearHighlights();
    this.highlights.clear();

    // Remove keyboard event listener
    const keyDownHandler = (this as any)._keyDownHandler;
    if (keyDownHandler) {
      document.removeEventListener('keydown', keyDownHandler);
      delete (this as any)._keyDownHandler;
    }

    this.container = null;
  }
}

/**
 * Utility function to create a highlighter instance
 */
export function createSearchHighlighter(options: SearchHighlighterOptions): SearchHighlighter {
  return new SearchHighlighter(options);
}

/**
 * Utility function to highlight text content (non-DOM version)
 */
export function highlightTextContent(
  content: string,
  searchResult: SearchResult,
  options: SearchHighlighterOptions
): string {
  if (!content) {
    return '';
  }
  const highlighter = new SearchHighlighter(options);
  const highlights = highlighter.processSearchResults(searchResult);

  if (highlights.length === 0) return content;

  let result = '';
  let lastIndex = 0;

  // Sort highlights by start position
  const sortedHighlights = [...highlights].sort((a, b) => a.start - b.start);

  for (const highlight of sortedHighlights) {
    // Add text before highlight
    if (highlight.start > lastIndex) {
      result += content.substring(lastIndex, highlight.start);
    }

    // Add highlighted text with HTML markup
    result += `<span class="${highlight.className}" data-highlight-id="${highlight.id}">`;
    result += highlight.text;
    result += '</span>';

    lastIndex = highlight.end;
  }

  // Add remaining text
  if (lastIndex < content.length) {
    result += content.substring(lastIndex);
  }

  return result;
}