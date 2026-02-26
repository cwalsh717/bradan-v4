/**
 * Subtle data freshness indicator with color-coded dot and relative time.
 * Green: < 1 hour, Yellow: < 24 hours, Red: > 24 hours (stale).
 */

import { formatRelativeTime } from "@/lib/format";

interface FreshnessIndicatorProps {
  timestamp: string | number | Date | null | undefined;
}

function freshnessColor(date: Date): string {
  const diffMs = Date.now() - date.getTime();
  const hours = diffMs / (1000 * 60 * 60);
  if (hours < 1) return "bg-green-500";
  if (hours < 24) return "bg-yellow-500";
  return "bg-red-500";
}

function toDate(ts: string | number | Date): Date {
  if (ts instanceof Date) return ts;
  if (typeof ts === "number") return new Date(ts * 1000);
  return new Date(ts);
}

export function FreshnessIndicator({ timestamp }: FreshnessIndicatorProps) {
  if (!timestamp && timestamp !== 0) return null;

  const date = toDate(timestamp);
  if (isNaN(date.getTime())) return null;

  return (
    <span
      className="inline-flex items-center gap-1 text-xs text-foreground/50"
      data-testid="freshness-indicator"
    >
      <span className={`inline-block h-1.5 w-1.5 rounded-full ${freshnessColor(date)}`} />
      {formatRelativeTime(date)}
    </span>
  );
}
