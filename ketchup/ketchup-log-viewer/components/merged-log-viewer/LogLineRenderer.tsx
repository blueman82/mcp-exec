/**
 * LogLineRenderer Component
 * Renders individual log lines with ANSI colors, timestamps, and search highlighting
 * Supports both virtualized (truncate) and non-virtualized (wrap) modes
 */

'use client';

import React from 'react';
import { parseAnsi, stripAnsi, segmentToStyle } from '@/lib/ansi-parser';
import { formatTimestamp, formatFullTimestamp, type TimestampMode } from '@/lib/timestamp-formatter';
import { getLogLevelBgColor } from '@/lib/log-level-detector';
import type { LogLine } from '@/types';

interface MergedLogLine extends LogLine {
  selectionKey: string;
}

interface LogLineRendererProps {
  log: MergedLogLine;
  index: number;
  isHighlighted: boolean;
  searchTerm: string;
  timestampMode: TimestampMode;
  theme: 'dark' | 'light';
  wrapLines: boolean;
  onCopyLine: (log: MergedLogLine) => void;
  onCopyFullLine: (log: MergedLogLine) => void;
  style?: React.CSSProperties;
}

const LogLineRenderer: React.FC<LogLineRendererProps> = ({
  log,
  index,
  isHighlighted,
  searchTerm,
  timestampMode,
  theme,
  wrapLines,
  onCopyLine,
  onCopyFullLine,
  style,
}) => {
  const segments = parseAnsi(log.content);
  const bgColor = log.level ? getLogLevelBgColor(log.level) : '';
  const serverBorderColor = log.server === 'prod1' ? 'border-l-blue-500' : 'border-l-green-500';
  const serverBadgeColor =
    log.server === 'prod1'
      ? 'bg-blue-600 text-white border-blue-500'
      : 'bg-green-600 text-white border-green-500';

  // Highlight search matches
  const highlightMatches = (text: string, search: string) => {
    if (!search.trim()) {
      return <>{text}</>;
    }

    const lowerText = text.toLowerCase();
    const lowerSearch = search.toLowerCase();
    const parts: React.JSX.Element[] = [];
    let lastIndex = 0;

    let idx = lowerText.indexOf(lowerSearch);
    while (idx !== -1) {
      if (idx > lastIndex) {
        parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex, idx)}</span>);
      }

      parts.push(
        <span
          key={`match-${idx}`}
          className="bg-yellow-500 text-black font-bold px-0.5 rounded"
        >
          {text.slice(idx, idx + search.length)}
        </span>
      );

      lastIndex = idx + search.length;
      idx = lowerText.indexOf(lowerSearch, lastIndex);
    }

    if (lastIndex < text.length) {
      parts.push(<span key={`text-${lastIndex}`}>{text.slice(lastIndex)}</span>);
    }

    return <>{parts}</>;
  };

  const baseClasses = `px-4 font-mono text-xs border-l-4 ${serverBorderColor} ${
    theme === 'dark' ? 'text-gray-300 hover:bg-gray-900' : 'text-gray-800 hover:bg-gray-200'
  }`;

  const combinedStyle = {
    ...style,
    backgroundColor: isHighlighted ? 'rgba(147, 51, 234, 0.3)' : bgColor,
    minHeight: wrapLines ? '24px' : undefined,
    lineHeight: wrapLines ? '1.5' : undefined,
    whiteSpace: wrapLines ? ('pre-wrap' as const) : ('nowrap' as const),
    overflowWrap: wrapLines ? ('break-word' as const) : undefined,
    wordBreak: wrapLines ? ('normal' as const) : undefined,
    paddingTop: wrapLines ? '4px' : undefined,
    paddingBottom: wrapLines ? '4px' : undefined,
  };

  return (
    <div style={combinedStyle} className={baseClasses}>
      <span
        className={`mr-2 cursor-pointer select-none ${
          theme === 'dark' ? 'text-gray-600 hover:text-blue-400' : 'text-gray-400 hover:text-blue-600'
        }`}
        onClick={(e) => {
          e.stopPropagation();
          if (e.shiftKey) {
            onCopyFullLine(log);
          } else {
            onCopyLine(log);
          }
        }}
        title="Click to copy line content\nShift+Click to copy with timestamp"
      >
        {index + 1}
      </span>
      <span className={`inline-block px-1.5 py-0.5 rounded text-[10px] font-bold mr-2 ${serverBadgeColor}`}>
        {log.server}
      </span>
      <span
        className={theme === 'dark' ? 'text-gray-500 mr-2' : 'text-gray-500 mr-2'}
        title={formatFullTimestamp(log.timestamp)}
      >
        [{formatTimestamp(log.timestamp, timestampMode)}]
      </span>
      <span className="text-gray-400 mr-2">{log.container}:</span>
      {segments.map((segment, idx) => (
        <span key={idx} style={segmentToStyle(segment)}>
          {highlightMatches(segment.text, searchTerm)}
        </span>
      ))}
    </div>
  );
};

export default LogLineRenderer;
