"use client";

import { useEffect, useState, useCallback } from "react";
import { API_BASE } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import type { DashboardCategory, PriceUpdate } from "@/lib/types";
import { CategorySection } from "@/components/dashboard/CategorySection";
import { ErrorState } from "@/components/ErrorState";

const CATEGORY_ORDER = [
  "equities",
  "rates",
  "credit",
  "currencies",
  "commodities",
  "critical_minerals",
  "crypto",
  "futures",
];

interface DashboardStream {
  prices: Record<string, { price: number; timestamp: string; change?: number; change_percent?: number }>;
}

function sortCategories(categories: DashboardCategory[]): DashboardCategory[] {
  return [...categories].sort((a, b) => {
    const ai = CATEGORY_ORDER.indexOf(a.name);
    const bi = CATEGORY_ORDER.indexOf(b.name);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
}

export default function DashboardPage() {
  const [categories, setCategories] = useState<DashboardCategory[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prices, setPrices] = useState<Record<string, PriceUpdate>>({});

  const fetchConfig = useCallback(() => {
    setLoading(true);
    setError(null);
    fetch(`${API_BASE}/api/dashboard/config`)
      .then((r) => {
        if (!r.ok) throw new Error(r.statusText);
        return r.json();
      })
      .then((data: { categories: DashboardCategory[] }) => {
        setCategories(sortCategories(data.categories));
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load dashboard data");
        setLoading(false);
      });
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  // Connect to live price stream
  const { data: streamData, isConnected } = useWebSocket<DashboardStream>(
    "/api/dashboard/stream",
    { enabled: !loading && categories != null },
  );

  // Merge incoming prices into state
  useEffect(() => {
    if (streamData?.prices) {
      setPrices((prev) => {
        const next = { ...prev };
        for (const [symbol, update] of Object.entries(streamData.prices)) {
          next[symbol] = { symbol, ...update };
        }
        return next;
      });
    }
  }, [streamData]);

  return (
    <main className="p-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold">Market Dashboard</h1>
        <p className="mt-1 text-foreground/60">Live market data</p>
      </div>

      {!isConnected && !loading && categories != null && (
        <div className="mb-6 rounded-md bg-yellow-50 px-4 py-2 text-sm text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-200">
          Live prices disconnected
        </div>
      )}

      {error && !loading && (
        <ErrorState message={error} onRetry={fetchConfig} />
      )}

      {loading ? (
        <div data-testid="dashboard-loading">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="mb-8">
              <div className="mb-3 h-6 w-32 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                {[...Array(4)].map((_, j) => (
                  <div
                    key={j}
                    className="h-24 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800"
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : categories != null ? (
        <div>
          {categories.map((cat) => (
            <CategorySection
              key={cat.name}
              name={cat.name}
              tickers={cat.tickers}
              prices={prices}
            />
          ))}
        </div>
      ) : null}
    </main>
  );
}
