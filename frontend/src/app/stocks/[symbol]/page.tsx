"use client";

import { use, useState, useEffect, useCallback } from "react";
import { apiGet } from "@/lib/api";
import { useWebSocket } from "@/lib/ws";
import { formatCurrency, formatChange, changeColor, formatDate } from "@/lib/format";
import { PriceChart } from "@/components/stocks/PriceChart";
import { FinancialsTable } from "@/components/stocks/FinancialsTable";
import { RatiosGrid } from "@/components/stocks/RatiosGrid";
import { PeerList } from "@/components/stocks/PeerList";
import type {
  StockProfile,
  FinancialRatios,
  FinancialStatement,
  Dividend,
  PeerStock,
  PriceUpdate,
} from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";
import { FreshnessIndicator } from "@/components/FreshnessIndicator";

interface StockProfilePageProps {
  params: Promise<{ symbol: string }>;
}

type TabId = "financials" | "ratios" | "dividends";

interface PriceHistoryPoint {
  date: string;
  close: number;
}

export default function StockProfilePage({ params }: StockProfilePageProps) {
  const { symbol } = use(params);
  const upperSymbol = symbol.toUpperCase();

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------
  const [profile, setProfile] = useState<StockProfile | null>(null);
  const [priceHistory, setPriceHistory] = useState<PriceHistoryPoint[] | null>(null);
  const [financials, setFinancials] = useState<FinancialStatement[] | null>(null);
  const [ratios, setRatios] = useState<FinancialRatios | null>(null);
  const [dividends, setDividends] = useState<Dividend[] | null>(null);
  const [peers, setPeers] = useState<PeerStock[] | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabId>("financials");

  // ---------------------------------------------------------------------------
  // Live price via WebSocket
  // ---------------------------------------------------------------------------
  const { data: livePrice } = useWebSocket<PriceUpdate>(
    `/api/stocks/${upperSymbol}/stream`,
  );

  // ---------------------------------------------------------------------------
  // Data fetching
  // ---------------------------------------------------------------------------
  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);

    const oneYearAgo = new Date();
    oneYearAgo.setFullYear(oneYearAgo.getFullYear() - 1);
    const startDate = oneYearAgo.toISOString().split("T")[0];

    const results = await Promise.allSettled([
      apiGet<StockProfile>(`/api/stocks/${upperSymbol}/profile`),
      apiGet<PriceHistoryPoint[]>(
        `/api/stocks/${upperSymbol}/price-history?start_date=${startDate}`,
      ),
      apiGet<FinancialStatement[]>(
        `/api/stocks/${upperSymbol}/financials?period=annual`,
      ),
      apiGet<FinancialRatios>(`/api/stocks/${upperSymbol}/ratios`),
      apiGet<Dividend[]>(`/api/stocks/${upperSymbol}/dividends`),
      apiGet<PeerStock[]>(`/api/stocks/${upperSymbol}/peers`),
    ]);

    const [profileRes, priceRes, finRes, ratiosRes, divRes, peersRes] = results;

    if (profileRes.status === "fulfilled") {
      setProfile(profileRes.value);
    } else {
      setError("Stock not found");
    }

    if (priceRes.status === "fulfilled") setPriceHistory(priceRes.value);
    if (finRes.status === "fulfilled") setFinancials(finRes.value);
    if (ratiosRes.status === "fulfilled") setRatios(ratiosRes.value);
    if (divRes.status === "fulfilled") setDividends(divRes.value);
    if (peersRes.status === "fulfilled") setPeers(peersRes.value);

    setLoading(false);
  }, [upperSymbol]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ---------------------------------------------------------------------------
  // Loading state
  // ---------------------------------------------------------------------------
  if (loading) {
    return (
      <main className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-64 rounded bg-foreground/10" />
          <div className="h-4 w-48 rounded bg-foreground/10" />
          <div className="h-[300px] rounded-lg bg-foreground/5" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-32 rounded-lg bg-foreground/5" />
            <div className="h-32 rounded-lg bg-foreground/5" />
            <div className="h-32 rounded-lg bg-foreground/5" />
          </div>
        </div>
      </main>
    );
  }

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------
  if (error && !profile) {
    return (
      <main className="p-8">
        <h1 className="text-2xl font-bold">{upperSymbol}</h1>
        <div className="mt-4">
          <ErrorState message={error} onRetry={fetchData} />
        </div>
      </main>
    );
  }

  // ---------------------------------------------------------------------------
  // Tab content
  // ---------------------------------------------------------------------------
  const tabs: { id: TabId; label: string }[] = [
    { id: "financials", label: "Financials" },
    { id: "ratios", label: "Ratios" },
    { id: "dividends", label: "Dividends & Splits" },
  ];

  const currentPrice = livePrice?.price ?? null;
  const priceChange = livePrice?.change_percent ?? null;

  return (
    <main className="p-8">
      {/* ------------------------------------------------------------------ */}
      {/* Header                                                             */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{profile?.name ?? upperSymbol}</h1>
            <span className="text-lg text-foreground/60">{upperSymbol}</span>
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-foreground/60">
            {profile?.exchange && <span>{profile.exchange}</span>}
            {profile?.sector && (
              <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs">
                {profile.sector}
              </span>
            )}
            {profile?.industry && (
              <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs">
                {profile.industry}
              </span>
            )}
            <FreshnessIndicator timestamp={profile?.last_updated} />
          </div>
        </div>

        {currentPrice != null && (
          <div className="text-right">
            <p className="text-3xl font-bold tabular-nums">
              {formatCurrency(currentPrice, profile?.currency)}
            </p>
            {priceChange != null && (
              <p className={`text-sm font-medium ${changeColor(priceChange)}`}>
                {formatChange(priceChange)}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Price Chart                                                        */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-8">
        <h2 className="mb-4 text-lg font-semibold">Price History</h2>
        {priceHistory != null ? (
          <PriceChart data={priceHistory} />
        ) : (
          <div className="flex h-[300px] items-center justify-center rounded-lg bg-foreground/5 text-foreground/40">
            Price history unavailable
          </div>
        )}
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Tabs                                                               */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-8">
        <div className="flex gap-1 border-b border-foreground/10">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${
                activeTab === tab.id
                  ? "border-b-2 border-foreground text-foreground"
                  : "text-foreground/50 hover:text-foreground/80"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="mt-6">
          {activeTab === "financials" && (
            financials != null ? (
              <FinancialsTable statements={financials} />
            ) : (
              <p className="py-8 text-center text-foreground/40">
                Financial data unavailable
              </p>
            )
          )}

          {activeTab === "ratios" && (
            ratios != null ? (
              <RatiosGrid ratios={ratios} />
            ) : (
              <p className="py-8 text-center text-foreground/40">
                Ratios unavailable
              </p>
            )
          )}

          {activeTab === "dividends" && (
            <div>
              {dividends != null && dividends.length > 0 ? (
                <div>
                  <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-foreground/60">
                    Dividends
                  </h3>
                  <ul className="divide-y divide-foreground/10">
                    {dividends.map((d) => (
                      <li
                        key={d.id}
                        className="flex items-center justify-between py-3"
                      >
                        <span className="text-sm text-foreground/60">
                          {formatDate(d.ex_date)}
                        </span>
                        <span className="font-semibold tabular-nums">
                          {formatCurrency(d.amount)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : (
                <p className="py-8 text-center text-foreground/40">
                  No dividend data available
                </p>
              )}
            </div>
          )}
        </div>
      </section>

      {/* ------------------------------------------------------------------ */}
      {/* Peers                                                              */}
      {/* ------------------------------------------------------------------ */}
      <section className="mt-8">
        <h2 className="mb-4 text-lg font-semibold">Peers</h2>
        {peers != null ? (
          <PeerList peers={peers} />
        ) : (
          <p className="text-sm text-foreground/40">Peer data unavailable</p>
        )}
      </section>
    </main>
  );
}
