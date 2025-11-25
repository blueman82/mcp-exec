/**
 * Custom ANSI escape code parser for terminal log output
 * No external dependencies - pure TypeScript implementation
 */

export interface AnsiSegment {
  text: string;
  style: {
    color?: string;
    backgroundColor?: string;
    bold?: boolean;
    dim?: boolean;
    italic?: boolean;
    underline?: boolean;
  };
}

// ANSI color code to CSS color mapping
const ANSI_COLORS: Record<number, string> = {
  30: '#000000', // Black
  31: '#CD3131', // Red
  32: '#0DBC79', // Green
  33: '#E5E510', // Yellow
  34: '#2472C8', // Blue
  35: '#BC3FBC', // Magenta
  36: '#11A8CD', // Cyan
  37: '#E5E5E5', // White
  90: '#666666', // Bright Black (Gray)
  91: '#F14C4C', // Bright Red
  92: '#23D18B', // Bright Green
  93: '#F5F543', // Bright Yellow
  94: '#3B8EEA', // Bright Blue
  95: '#D670D6', // Bright Magenta
  96: '#29B8DB', // Bright Cyan
  97: '#FFFFFF', // Bright White
};

const ANSI_BG_COLORS: Record<number, string> = {
  40: '#000000',
  41: '#CD3131',
  42: '#0DBC79',
  43: '#E5E510',
  44: '#2472C8',
  45: '#BC3FBC',
  46: '#11A8CD',
  47: '#E5E5E5',
  100: '#666666',
  101: '#F14C4C',
  102: '#23D18B',
  103: '#F5F543',
  104: '#3B8EEA',
  105: '#D670D6',
  106: '#29B8DB',
  107: '#FFFFFF',
};

/**
 * Parse ANSI escape codes and return styled segments
 */
export function parseAnsi(text: string): AnsiSegment[] {
  const segments: AnsiSegment[] = [];
  const ansiRegex = /\u001b\[([0-9;]*)m/g;

  let currentStyle: AnsiSegment['style'] = {};
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = ansiRegex.exec(text)) !== null) {
    // Add text before this escape code
    if (match.index > lastIndex) {
      const textSegment = text.substring(lastIndex, match.index);
      if (textSegment) {
        segments.push({ text: textSegment, style: { ...currentStyle } });
      }
    }

    // Parse the escape code
    const codes = match[1].split(';').map(Number);
    currentStyle = applyAnsiCodes(codes, currentStyle);

    lastIndex = match.index + match[0].length;
  }

  // Add remaining text
  if (lastIndex < text.length) {
    const textSegment = text.substring(lastIndex);
    if (textSegment) {
      segments.push({ text: textSegment, style: { ...currentStyle } });
    }
  }

  // If no ANSI codes found, return plain text
  if (segments.length === 0 && text) {
    segments.push({ text, style: {} });
  }

  return segments;
}

/**
 * Apply ANSI codes to current style
 */
function applyAnsiCodes(
  codes: number[],
  currentStyle: AnsiSegment['style']
): AnsiSegment['style'] {
  const newStyle = { ...currentStyle };

  for (const code of codes) {
    if (code === 0) {
      // Reset all styles
      return {};
    } else if (code === 1) {
      newStyle.bold = true;
    } else if (code === 2) {
      newStyle.dim = true;
    } else if (code === 3) {
      newStyle.italic = true;
    } else if (code === 4) {
      newStyle.underline = true;
    } else if (code === 22) {
      newStyle.bold = false;
      newStyle.dim = false;
    } else if (code === 23) {
      newStyle.italic = false;
    } else if (code === 24) {
      newStyle.underline = false;
    } else if (ANSI_COLORS[code]) {
      newStyle.color = ANSI_COLORS[code];
    } else if (ANSI_BG_COLORS[code]) {
      newStyle.backgroundColor = ANSI_BG_COLORS[code];
    }
  }

  return newStyle;
}

/**
 * Strip ANSI codes from text (for search/filtering)
 */
export function stripAnsi(text: string): string {
  return text.replace(/\u001b\[[0-9;]*m/g, '');
}

/**
 * Convert parsed segments to inline CSS styles object
 */
export function segmentToStyle(segment: AnsiSegment): React.CSSProperties {
  const style: React.CSSProperties = {};

  if (segment.style.color) {
    style.color = segment.style.color;
  }
  if (segment.style.backgroundColor) {
    style.backgroundColor = segment.style.backgroundColor;
  }
  if (segment.style.bold) {
    style.fontWeight = 'bold';
  }
  if (segment.style.dim) {
    style.opacity = 0.6;
  }
  if (segment.style.italic) {
    style.fontStyle = 'italic';
  }
  if (segment.style.underline) {
    style.textDecoration = 'underline';
  }

  return style;
}
