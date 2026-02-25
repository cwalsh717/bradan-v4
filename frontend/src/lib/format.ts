/**
 * Number and price formatting helpers used across all pages.
 * All functions handle null/undefined inputs gracefully, returning an em dash.
 */

const EM_DASH = "\u2014";

/**
 * Format as currency: $1,234.56
 * Handles negatives: -$1,234.56
 */
export function formatCurrency(
  value: number | null | undefined,
  currency: string = "USD",
): string {
  if (value == null || isNaN(value)) return EM_DASH;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

/**
 * Format as percentage: 12.34%
 * Handles negatives with sign.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 2,
): string {
  if (value == null || isNaN(value)) return EM_DASH;
  return `${value.toFixed(decimals)}%`;
}

/**
 * Format large numbers: 1.2B, 345.6M, 12.3K
 * Numbers under 1000 are shown as-is with 2 decimal places.
 */
export function formatLargeNumber(
  value: number | null | undefined,
): string {
  if (value == null || isNaN(value)) return EM_DASH;

  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";

  if (abs >= 1_000_000_000) {
    return `${sign}${(abs / 1_000_000_000).toFixed(1)}B`;
  }
  if (abs >= 1_000_000) {
    return `${sign}${(abs / 1_000_000).toFixed(1)}M`;
  }
  if (abs >= 1_000) {
    return `${sign}${(abs / 1_000).toFixed(1)}K`;
  }
  return `${sign}${abs.toFixed(2)}`;
}

/**
 * Format with sign: +5.23% or -2.14%
 */
export function formatChange(
  value: number | null | undefined,
): string {
  if (value == null || isNaN(value)) return EM_DASH;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

/**
 * Get CSS class for positive/negative values.
 * Returns "text-green-500" for positive, "text-red-500" for negative, "text-gray-500" for zero/null.
 */
export function changeColor(
  value: number | null | undefined,
): string {
  if (value == null || isNaN(value) || value === 0) return "text-gray-500";
  return value > 0 ? "text-green-500" : "text-red-500";
}

/**
 * Format a date: "Jan 15, 2026"
 */
export function formatDate(
  dateStr: string | null | undefined,
): string {
  if (!dateStr) return EM_DASH;
  try {
    const date = new Date(dateStr);
    if (isNaN(date.getTime())) return EM_DASH;
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return EM_DASH;
  }
}

/**
 * Format ratio (2 decimal places, or "N/A").
 */
export function formatRatio(
  value: number | null | undefined,
): string {
  if (value == null || isNaN(value)) return "N/A";
  return value.toFixed(2);
}
