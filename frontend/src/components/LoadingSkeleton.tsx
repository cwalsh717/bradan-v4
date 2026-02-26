/**
 * Reusable loading skeleton with variant support.
 * Uses Tailwind animate-pulse for a shimmer effect.
 */

import type { JSX } from "react";

interface LoadingSkeletonProps {
  variant?: "card" | "table" | "chart" | "text";
  count?: number;
}

const skeletons: Record<string, () => JSX.Element> = {
  card: () => (
    <div className="h-24 animate-pulse rounded-lg bg-foreground/5" />
  ),
  table: () => (
    <div className="space-y-2">
      <div className="h-8 animate-pulse rounded bg-foreground/10" />
      {[...Array(5)].map((_, i) => (
        <div key={i} className="h-6 animate-pulse rounded bg-foreground/5" />
      ))}
    </div>
  ),
  chart: () => (
    <div className="h-[300px] animate-pulse rounded-lg bg-foreground/5" />
  ),
  text: () => (
    <div className="space-y-2">
      <div className="h-4 w-3/4 animate-pulse rounded bg-foreground/10" />
      <div className="h-4 w-1/2 animate-pulse rounded bg-foreground/10" />
    </div>
  ),
};

export function LoadingSkeleton({
  variant = "card",
  count = 1,
}: LoadingSkeletonProps) {
  const Skeleton = skeletons[variant] ?? skeletons.card;
  return (
    <div className="space-y-4" data-testid={`skeleton-${variant}`}>
      {[...Array(count)].map((_, i) => (
        <Skeleton key={i} />
      ))}
    </div>
  );
}
