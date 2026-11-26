export function normalizeForComparison(value: string): string[] {
  return value.toLocaleLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
}

export function wordErrorRate(reference: string, recognized: string): number | null {
  const target = normalizeForComparison(reference); const actual = normalizeForComparison(recognized);
  if (!target.length) return null;
  const row = Array.from({ length: actual.length + 1 }, (_, index) => index);
  for (let i = 1; i <= target.length; i += 1) { let previous = row[0]; row[0] = i; for (let j = 1; j <= actual.length; j += 1) { const saved = row[j]; row[j] = Math.min(row[j] + 1, row[j - 1] + 1, previous + Number(target[i - 1] !== actual[j - 1])); previous = saved; } }
  return row[actual.length] / target.length;
}
