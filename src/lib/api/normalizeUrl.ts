/**
 * Normalize a backend-provided URL/path into a browser-facing API URL.
 *
 * Rules:
 * - null/undefined/empty -> null
 * - Already absolute (http:// or https://) -> return as-is
 * - Already starts with /api/v1 -> return as-is
 * - Relative path starting with / but not /api/v1 -> prepend /api/v1
 * - Anything else -> return as-is (fallback)
 */
export function normalizeApiUrl(url: string | null | undefined): string | null {
  if (!url) return null;

  if (/^https?:\/\//i.test(url)) {
    return url;
  }

  if (url.startsWith('/api/v1')) {
    return url;
  }

  if (url.startsWith('/')) {
    return `/api/v1${url}`;
  }

  return url;
}
