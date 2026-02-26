"use client";

import { use, useEffect, useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { authFetch } from "@/lib/api";
import { formatCurrency, formatChange, changeColor, formatDate } from "@/lib/format";
import type { Portfolio, Holding, PerformanceSummary } from "@/lib/types";
import { ErrorState } from "@/components/ErrorState";

interface PortfolioDetailProps {
  params: Promise<{ id: string }>;
}

export default function PortfolioDetailPage({ params }: PortfolioDetailProps) {
  const { id } = use(params);
  const portfolioId = parseInt(id, 10);
  const { getToken } = useAuth();

  const [portfolio, setPortfolio] = useState<Portfolio | null>(null);
  const [performance, setPerformance] = useState<PerformanceSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Add holding state
  const [showAddHolding, setShowAddHolding] = useState(false);
  const [stockId, setStockId] = useState("");
  const [shares, setShares] = useState("");
  const [costBasis, setCostBasis] = useState("");

  const fetchData = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;

      const [portfolios, perf] = await Promise.all([
        authFetch<Portfolio[]>("/api/portfolios", token),
        authFetch<PerformanceSummary>(
          `/api/portfolios/${portfolioId}/performance`,
          token,
        ),
      ]);

      const found = portfolios.find((p) => p.id === portfolioId);
      setPortfolio(found ?? null);
      setPerformance(perf);
    } catch {
      setError("Failed to load portfolio");
    } finally {
      setLoading(false);
    }
  }, [getToken, portfolioId]);

  useEffect(() => { fetchData(); }, [fetchData]);

  const handleAddHolding = async () => {
    const sid = parseInt(stockId, 10);
    if (isNaN(sid)) return;
    try {
      const token = await getToken();
      if (!token) return;
      await authFetch<Holding>(`/api/portfolios/${portfolioId}/holdings`, token, {
        method: "POST",
        body: JSON.stringify({
          stock_id: sid,
          shares: shares ? parseFloat(shares) : null,
          cost_basis_per_share: costBasis ? parseFloat(costBasis) : null,
        }),
      });
      setStockId("");
      setShares("");
      setCostBasis("");
      setShowAddHolding(false);
      await fetchData();
    } catch {
      setError("Failed to add holding");
    }
  };

  const handleRemoveHolding = async (holdingId: number) => {
    try {
      const token = await getToken();
      if (!token) return;
      await authFetch<void>(
        `/api/portfolios/${portfolioId}/holdings/${holdingId}`,
        token,
        { method: "DELETE" },
      );
      await fetchData();
    } catch {
      setError("Failed to remove holding");
    }
  };

  if (loading) {
    return (
      <main className="p-8" data-testid="detail-loading">
        <div className="mb-4 h-8 w-48 animate-pulse rounded bg-gray-200 dark:bg-gray-700" />
        <div className="h-32 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
      </main>
    );
  }

  if (!portfolio) {
    return (
      <main className="p-8">
        <p className="text-foreground/60">Portfolio not found.</p>
        <Link href="/portfolio" className="mt-2 text-sm underline">
          Back to portfolios
        </Link>
      </main>
    );
  }

  const holdings = performance?.holdings ?? [];

  return (
    <main className="p-8">
      {/* Header */}
      <div className="mb-6">
        <Link href="/portfolio" className="text-sm text-foreground/60 hover:underline">
          &larr; All Portfolios
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-bold">{portfolio.name}</h1>
          <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs">
            {portfolio.mode}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4">
          <ErrorState message={error} onRetry={fetchData} />
        </div>
      )}

      {/* Performance Summary — only in full mode */}
      {portfolio.mode === "full" && performance && (
        <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4" data-testid="performance-summary">
          <div className="rounded-lg border border-foreground/10 p-4">
            <p className="text-sm text-foreground/60">Total Value</p>
            <p className="text-lg font-semibold">{formatCurrency(performance.total_value)}</p>
          </div>
          <div className="rounded-lg border border-foreground/10 p-4">
            <p className="text-sm text-foreground/60">Cost Basis</p>
            <p className="text-lg font-semibold">{formatCurrency(performance.total_cost_basis)}</p>
          </div>
          <div className="rounded-lg border border-foreground/10 p-4">
            <p className="text-sm text-foreground/60">Gain/Loss</p>
            <p className={`text-lg font-semibold ${changeColor(performance.total_gain_loss)}`}>
              {formatCurrency(performance.total_gain_loss)}
            </p>
          </div>
          <div className="rounded-lg border border-foreground/10 p-4">
            <p className="text-sm text-foreground/60">Return</p>
            <p className={`text-lg font-semibold ${changeColor(performance.total_gain_loss_pct)}`}>
              {formatChange(performance.total_gain_loss_pct)}
            </p>
          </div>
        </div>
      )}

      {/* Add Holding Button */}
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Holdings ({holdings.length})
        </h2>
        <button
          onClick={() => setShowAddHolding(!showAddHolding)}
          className="rounded-md bg-foreground px-3 py-1.5 text-sm font-medium text-background"
        >
          Add Holding
        </button>
      </div>

      {showAddHolding && (
        <div className="mb-4 rounded-lg border border-foreground/10 p-4" data-testid="add-holding-form">
          <div className="flex gap-3">
            <input
              type="number"
              placeholder="Stock ID"
              value={stockId}
              onChange={(e) => setStockId(e.target.value)}
              className="w-24 rounded-md border border-foreground/20 bg-transparent px-3 py-2 text-sm"
              data-testid="stock-id-input"
            />
            {portfolio.mode === "full" && (
              <>
                <input
                  type="number"
                  placeholder="Shares"
                  value={shares}
                  onChange={(e) => setShares(e.target.value)}
                  className="w-24 rounded-md border border-foreground/20 bg-transparent px-3 py-2 text-sm"
                  data-testid="shares-input"
                />
                <input
                  type="number"
                  placeholder="Cost basis"
                  value={costBasis}
                  onChange={(e) => setCostBasis(e.target.value)}
                  className="w-28 rounded-md border border-foreground/20 bg-transparent px-3 py-2 text-sm"
                  data-testid="cost-basis-input"
                />
              </>
            )}
            <button
              onClick={handleAddHolding}
              className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background"
              data-testid="add-holding-submit"
            >
              Add
            </button>
          </div>
        </div>
      )}

      {/* Holdings Table */}
      {holdings.length === 0 ? (
        <div className="rounded-lg border border-foreground/10 p-8 text-center text-foreground/60">
          No holdings yet. Add stocks to your portfolio.
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="holdings-table">
            <thead>
              <tr className="border-b border-foreground/10 text-left text-foreground/60">
                <th className="pb-2 pr-4">Symbol</th>
                <th className="pb-2 pr-4">Name</th>
                <th className="pb-2 pr-4 text-right">Price</th>
                {portfolio.mode === "full" && (
                  <>
                    <th className="pb-2 pr-4 text-right">Shares</th>
                    <th className="pb-2 pr-4 text-right">Cost Basis</th>
                    <th className="pb-2 pr-4 text-right">Market Value</th>
                    <th className="pb-2 pr-4 text-right">Gain/Loss</th>
                  </>
                )}
                <th className="pb-2"></th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.id} className="border-b border-foreground/5" data-testid={`holding-${h.id}`}>
                  <td className="py-3 pr-4">
                    <Link href={`/stocks/${h.symbol}`} className="font-medium hover:underline">
                      {h.symbol}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-foreground/80">{h.name}</td>
                  <td className="py-3 pr-4 text-right">{formatCurrency(h.current_price)}</td>
                  {portfolio.mode === "full" && (
                    <>
                      <td className="py-3 pr-4 text-right">{h.shares ?? "\u2014"}</td>
                      <td className="py-3 pr-4 text-right">{formatCurrency(h.cost_basis_per_share)}</td>
                      <td className="py-3 pr-4 text-right">{formatCurrency(h.market_value)}</td>
                      <td className={`py-3 pr-4 text-right ${changeColor(h.gain_loss)}`}>
                        {formatCurrency(h.gain_loss)}
                        {h.gain_loss_pct != null && (
                          <span className="ml-1 text-xs">({formatChange(h.gain_loss_pct)})</span>
                        )}
                      </td>
                    </>
                  )}
                  <td className="py-3 text-right">
                    <button
                      onClick={() => handleRemoveHolding(h.id)}
                      className="text-xs text-red-500 hover:text-red-700"
                      data-testid={`remove-${h.id}`}
                    >
                      Remove
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </main>
  );
}
