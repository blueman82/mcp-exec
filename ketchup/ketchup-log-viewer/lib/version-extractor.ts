/**
 * Docker Image Version Extractor
 * Extracts semantic version from ECR image tags
 */

/**
 * Extract version from Docker image string
 * @param image - Full Docker image path (e.g., "ecr.../ketchup-app:v2.360.236")
 * @returns Version string (e.g., "v2.360.236") or null if not found
 */
export function extractVersion(image: string): string | null {
  if (!image) return null;

  // Split by ':' to get tag portion
  const parts = image.split(':');
  if (parts.length < 2) return null;

  const tag = parts[parts.length - 1];

  // Match semantic version pattern (v2.xxx.xxx or 2.xxx.xxx)
  const versionMatch = tag.match(/v?\d+\.\d+\.\d+/);

  if (versionMatch) {
    const version = versionMatch[0];
    // Ensure 'v' prefix for consistency
    return version.startsWith('v') ? version : `v${version}`;
  }

  // If tag is 'latest' or no version found, return tag as-is
  return tag === 'latest' ? 'latest' : null;
}

/**
 * Get display-friendly version with color coding
 * @param version - Version string from extractVersion()
 * @returns Object with version and color class for styling
 */
export function getVersionDisplay(version: string | null): {
  text: string;
  colorClass: string;
} {
  if (!version) {
    return {
      text: 'unknown',
      colorClass: 'text-gray-500',
    };
  }

  if (version === 'latest') {
    return {
      text: 'latest',
      colorClass: 'text-yellow-400',
    };
  }

  // Semantic version (v2.xxx.xxx)
  return {
    text: version,
    colorClass: 'text-blue-400',
  };
}
