/**
 * Sequence hash utility.
 *
 * WHY THIS EXISTS:
 * The original target-protein flow used `crypto.subtle.digest('SHA-256', ...)`.
 * The Web Crypto `crypto.subtle` API is ONLY available in secure contexts
 * (HTTPS or localhost). The STAMP preview is served over plain HTTP at a
 * LAN/Tailscale IP (http://100.75.69.36:12833), which is NOT a secure context,
 * so `window.crypto.subtle` is `undefined` and `crypto.subtle.digest(...)`
 * throws: "Cannot read properties of undefined (reading 'digest')".
 *
 * This util uses Web Crypto SHA-256 when available (secure context), and falls
 * back to a synchronous non-cryptographic hash (cyrb53) otherwise so the
 * target-protein flow still works over HTTP. The hash is used only as a short
 * dedup/index key (16 hex chars), NOT for any security purpose, so a
 * non-cryptographic fallback is acceptable and clearly labeled.
 */

function cyrb53(str: string, seed = 0): string {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  const hex = (4294967296 * (2097151 & h2) + (h1 >>> 0)).toString(16);
  return hex.padStart(14, '0');
}

/**
 * Compute a 16-char hex hash of a protein sequence.
 * Uses Web Crypto SHA-256 in secure contexts; falls back to cyrb53 over HTTP.
 */
export async function sequenceHash(sequence: string): Promise<string> {
  const data = new TextEncoder().encode(sequence);
  const subtle = globalThis.crypto?.subtle;
  if (subtle && typeof subtle.digest === 'function') {
    try {
      const buf = await subtle.digest('SHA-256', data);
      return Array.from(new Uint8Array(buf))
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('')
        .slice(0, 16);
    } catch {
      // fall through to synchronous fallback
    }
  }
  // Non-secure context (HTTP non-localhost): synchronous fallback.
  return cyrb53(sequence).slice(0, 16);
}

/** True when Web Crypto SHA-256 is available (i.e. a secure context). */
export function hasWebCryptoSubtle(): boolean {
  return !!(globalThis.crypto?.subtle && typeof globalThis.crypto.subtle.digest === 'function');
}
