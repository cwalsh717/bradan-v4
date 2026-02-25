"use client";

import { useEffect, useRef, useState } from "react";
import type { DashboardTicker, PriceUpdate } from "@/lib/types";
import {
  formatCurrency,
  formatPercent,
  formatChange,
  changeColor,
} from "@/lib/format";

interface TickerCardProps {
  ticker: DashboardTicker;
  price: PriceUpdate | null;
}

export function TickerCard({ ticker, price }: TickerCardProps) {
  const [flash, setFlash] = useState(false);
  const prevPriceRef = useRef<number | null>(null);

  useEffect(() => {
    if (price && price.price !== prevPriceRef.current) {
      prevPriceRef.current = price.price;
      setFlash(true);
      const timer = setTimeout(() => setFlash(false), 400);
      return () => clearTimeout(timer);
    }
  }, [price]);

  const formattedPrice =
    price != null
      ? ticker.display_format === "percentage"
        ? formatPercent(price.price)
        : formatCurrency(price.price)
      : null;

  return (
    <div
      className={`rounded-lg border border-gray-200 p-4 transition-colors duration-300 dark:border-gray-700 ${
        flash ? "bg-blue-50 dark:bg-blue-950" : "bg-white dark:bg-gray-900"
      }`}
      data-testid={`ticker-card-${ticker.symbol}`}
    >
      <div className="mb-1 text-sm text-foreground/60">{ticker.display_name}</div>
      {formattedPrice != null ? (
        <>
          <div className="text-xl font-semibold">{formattedPrice}</div>
          <div className={`text-sm ${changeColor(price?.change_percent)}`}>
            {formatChange(price?.change_percent)}
          </div>
        </>
      ) : (
        <div className="text-xl text-foreground/30">&mdash;</div>
      )}
    </div>
  );
}
