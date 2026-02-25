"use client";

import type { DashboardTicker, PriceUpdate } from "@/lib/types";
import { TickerCard } from "./TickerCard";

interface CategorySectionProps {
  name: string;
  tickers: DashboardTicker[];
  prices: Record<string, PriceUpdate>;
}

export function CategorySection({ name, tickers, prices }: CategorySectionProps) {
  const displayName = name.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  return (
    <section className="mb-8" data-testid={`category-${name}`}>
      <h2 className="mb-3 text-lg font-semibold">{displayName}</h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {tickers.map((ticker) => (
          <TickerCard
            key={ticker.symbol}
            ticker={ticker}
            price={prices[ticker.symbol] ?? null}
          />
        ))}
      </div>
    </section>
  );
}
