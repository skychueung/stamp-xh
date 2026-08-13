export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toFixed(2);
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return value.toLocaleString();
}

export function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

export function formatSequence(seq: string, maxLen: number = 40): string {
  if (!seq) return "-";
  if (seq.length <= maxLen) return seq;
  return `${seq.slice(0, maxLen)}...`;
}
