"use client";

import { use, useState, useEffect, useCallback } from "react";
import { apiFetch } from "@/lib/api";
import type { DCFResult, SensitivityMatrix, DCFConstraints } from "@/lib/types";
import { Headline } from "@/components/dcf/Headline";
import { AssumptionCards } from "@/components/dcf/AssumptionCards";
import { ScenarioSelector } from "@/components/dcf/ScenarioSelector";
import { EquityBridge } from "@/components/dcf/EquityBridge";
import { ProjectionTable } from "@/components/dcf/ProjectionTable";
import { SensitivityTable } from "@/components/dcf/SensitivityTable";
import { formatPercent, formatLargeNumber } from "@/lib/format";
import { ErrorState } from "@/components/ErrorState";
import { FreshnessIndicator } from "@/components/FreshnessIndicator";

interface DCFPageProps {
  params: Promise<{ symbol: string }>;
}

export default function DCFPage({ params }: DCFPageProps) {
  const { symbol } = use(params);
  const upperSymbol = symbol.toUpperCase();

  const [result, setResult] = useState<DCFResult | null>(null);
  const [sensitivity, setSensitivity] = useState<SensitivityMatrix | null>(null);
  const [constraints, setConstraints] = useState<DCFConstraints | null>(null);
  const [activeScenario, setActiveScenario] = useState("moderate");
  const [showDetails, setShowDetails] = useState(false);
  const [showFullModel, setShowFullModel] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [fetchKey, setFetchKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);
      try {
        const [dcfRes, sensRes, constraintRes] = await Promise.all([
          apiFetch<DCFResult>(`/api/dcf/${upperSymbol}/default`),
          apiFetch<SensitivityMatrix>(`/api/dcf/${upperSymbol}/sensitivity`),
          apiFetch<DCFConstraints>(`/api/dcf/constraints`),
        ]);

        if (!cancelled) {
          setResult(dcfRes.data);
          setSensitivity(sensRes.data);
          setConstraints(constraintRes.data);
          setActiveScenario(dcfRes.data.scenario || "moderate");
        }
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to load DCF data",
          );
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchData();
    return () => {
      cancelled = true;
    };
  }, [upperSymbol, fetchKey]);

  const retryFetch = useCallback(() => {
    setFetchKey((k) => k + 1);
  }, []);

  const handleScenarioSelect = useCallback(
    async (scenario: string) => {
      setActiveScenario(scenario);
      try {
        const res = await apiFetch<DCFResult>(
          `/api/dcf/${upperSymbol}/compute`,
          {
            method: "POST",
            body: JSON.stringify({ scenario }),
          },
        );
        setResult(res.data);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to compute scenario",
        );
      }
    },
    [upperSymbol],
  );

  if (loading) {
    return (
      <main className="p-8">
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-64 rounded bg-foreground/10" />
          <div className="h-4 w-48 rounded bg-foreground/10" />
          <div className="grid grid-cols-3 gap-4">
            <div className="h-24 rounded-lg bg-foreground/5" />
            <div className="h-24 rounded-lg bg-foreground/5" />
            <div className="h-24 rounded-lg bg-foreground/5" />
          </div>
        </div>
      </main>
    );
  }

  if (error || !result) {
    return (
      <main className="p-8">
        <h1 className="text-2xl font-bold">DCF — {upperSymbol}</h1>
        <div className="mt-2">
          <ErrorState
            message={error || "No data available"}
            onRetry={retryFetch}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="p-8">
      {/* Level 1: Headline — always visible */}
      <Headline result={result} />
      <div className="mt-2">
        <FreshnessIndicator timestamp={result.computed_at} />
      </div>

      <div className="mt-6">
        <button
          onClick={() => setShowDetails(!showDetails)}
          className="text-sm font-medium text-blue-600 hover:text-blue-800"
        >
          {showDetails ? "Hide Details" : "Show Details"}
        </button>
      </div>

      {/* Level 2: Overview — expandable */}
      {showDetails && (
        <div className="mt-6 space-y-6">
          <AssumptionCards result={result} />
          <ScenarioSelector
            activeScenario={activeScenario}
            onSelect={handleScenarioSelect}
          />
          <EquityBridge bridge={result.equity_bridge} />

          <div className="mt-4">
            <button
              onClick={() => setShowFullModel(!showFullModel)}
              className="text-sm font-medium text-blue-600 hover:text-blue-800"
            >
              {showFullModel ? "Hide Full Model" : "Show Full Model"}
            </button>
          </div>

          {/* Level 3: Full Model — expandable */}
          {showFullModel && (
            <div className="space-y-6">
              <ProjectionTable
                projections={result.projections}
                terminal={result.terminal}
              />

              {sensitivity && (
                <SensitivityTable
                  matrix={sensitivity}
                  currentPrice={result.current_price}
                />
              )}

              {/* Terminal Value Info */}
              <div className="rounded-lg border border-foreground/10 p-4">
                <h3 className="mb-3 text-sm font-semibold text-foreground/70 uppercase tracking-wide">
                  Terminal Value
                </h3>
                <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3 lg:grid-cols-5">
                  <div>
                    <p className="text-foreground/60">Terminal Growth</p>
                    <p className="font-semibold">
                      {formatPercent(result.terminal.terminal_growth * 100)}
                    </p>
                  </div>
                  <div>
                    <p className="text-foreground/60">Terminal WACC</p>
                    <p className="font-semibold">
                      {formatPercent(result.terminal.terminal_wacc * 100)}
                    </p>
                  </div>
                  <div>
                    <p className="text-foreground/60">Terminal Value</p>
                    <p className="font-semibold">
                      {formatLargeNumber(result.terminal.terminal_value)}
                    </p>
                  </div>
                  <div>
                    <p className="text-foreground/60">PV of Terminal</p>
                    <p className="font-semibold">
                      {formatLargeNumber(result.terminal.pv_terminal)}
                    </p>
                  </div>
                  <div>
                    <p className="text-foreground/60">% of Total Value</p>
                    <p className="font-semibold">
                      {formatPercent(result.terminal_value_pct * 100)}
                    </p>
                  </div>
                </div>
              </div>

              {/* CSV Export */}
              <div>
                <a
                  href={`${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"}/api/dcf/${upperSymbol}/runs/default/export?format=csv`}
                  className="inline-flex items-center rounded-lg border border-foreground/20 px-4 py-2 text-sm font-medium hover:bg-foreground/5"
                  download
                >
                  Download CSV
                </a>
              </div>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
