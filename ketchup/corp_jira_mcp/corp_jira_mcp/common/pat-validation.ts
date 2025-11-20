// PAT validation utilities

export function isValidPatFormat(pat: string): boolean {
  if (!pat || typeof pat !== 'string') {
    return false;
  }
  // PAT should be non-empty string, typically alphanumeric with hyphens and underscores
  return /^[a-zA-Z0-9_\-]+$/.test(pat) && pat.length > 0;
}
