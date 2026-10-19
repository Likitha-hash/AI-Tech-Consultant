/** "Unchanged" = at least 98% similar after collapsing whitespace. Typos count as changes; line-wrap does not. */
export const UNCHANGED_THRESHOLD = 0.98;

export function normalize(s: string): string {
  return s.replace(/\s+/g, " ").trim();
}

export function similarity(a: string, b: string): number {
  const x = normalize(a), y = normalize(b);
  if (x === y) return 1;
  if (!x.length || !y.length) return 0;
  let prev = Array.from({ length: y.length + 1 }, (_, j) => j);
  for (let i = 1; i <= x.length; i++) {
    const cur = [i];
    for (let j = 1; j <= y.length; j++) {
      cur[j] = Math.min((prev[j] ?? 0) + 1, (cur[j - 1] ?? 0) + 1, (prev[j - 1] ?? 0) + (x[i - 1] === y[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return 1 - (prev[y.length] ?? 0) / Math.max(x.length, y.length);
}
