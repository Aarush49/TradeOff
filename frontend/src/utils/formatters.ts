export const money = (n?: number | null): string =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: 0,
  }).format(n ?? 0);

export const pct = (n?: number | null): string =>
  `${((n ?? 0) * 100).toFixed(1)}%`;

export const date = (t: string | number | Date): string =>
  new Date(t).toLocaleString();
