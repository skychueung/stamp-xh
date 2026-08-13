const VALID_AA = new Set([
  "A", "C", "D", "E", "F", "G", "H", "I", "K", "L",
  "M", "N", "P", "Q", "R", "S", "T", "V", "W", "Y",
]);

export function validateSequence(seq: string): boolean {
  if (!seq || seq.length === 0) return false;
  const upper = seq.toUpperCase();
  for (const char of upper) {
    if (!VALID_AA.has(char)) return false;
  }
  return true;
}

export function cleanSequence(seq: string): string {
  return seq.replace(/\s/g, "").toUpperCase();
}

export function getSequenceLength(seq: string): number {
  return cleanSequence(seq).length;
}
