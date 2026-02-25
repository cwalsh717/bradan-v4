"use client";

import { useEffect, useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { authFetch } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { Portfolio } from "@/lib/types";

export default function PortfolioPage() {
  const { getToken } = useAuth();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newMode, setNewMode] = useState<"watchlist" | "full">("watchlist");
  const [error, setError] = useState<string | null>(null);

  const fetchPortfolios = useCallback(async () => {
    try {
      const token = await getToken();
      if (!token) return;
      const data = await authFetch<Portfolio[]>("/api/portfolios", token);
      setPortfolios(data);
    } catch {
      setError("Failed to load portfolios");
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => { fetchPortfolios(); }, [fetchPortfolios]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    try {
      const token = await getToken();
      if (!token) return;
      await authFetch<Portfolio>("/api/portfolios", token, {
        method: "POST",
        body: JSON.stringify({ name: newName.trim(), mode: newMode }),
      });
      setNewName("");
      setNewMode("watchlist");
      setShowCreate(false);
      await fetchPortfolios();
    } catch {
      setError("Failed to create portfolio");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      const token = await getToken();
      if (!token) return;
      await authFetch<void>(`/api/portfolios/${id}`, token, { method: "DELETE" });
      await fetchPortfolios();
    } catch {
      setError("Failed to delete portfolio");
    }
  };

  return (
    <main className="p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Portfolio</h1>
          <p className="mt-1 text-foreground/60">Manage your stock portfolios</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background transition-colors hover:bg-foreground/90"
        >
          New Portfolio
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md bg-red-50 px-4 py-2 text-sm text-red-800 dark:bg-red-900/30 dark:text-red-200">
          {error}
        </div>
      )}

      {showCreate && (
        <div className="mb-6 rounded-lg border border-foreground/10 p-4" data-testid="create-form">
          <div className="flex gap-3">
            <input
              type="text"
              placeholder="Portfolio name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="flex-1 rounded-md border border-foreground/20 bg-transparent px-3 py-2 text-sm"
              data-testid="portfolio-name-input"
            />
            <select
              value={newMode}
              onChange={(e) => setNewMode(e.target.value as "watchlist" | "full")}
              className="rounded-md border border-foreground/20 bg-transparent px-3 py-2 text-sm"
              data-testid="portfolio-mode-select"
            >
              <option value="watchlist">Watchlist</option>
              <option value="full">Full (P&amp;L)</option>
            </select>
            <button
              onClick={handleCreate}
              className="rounded-md bg-foreground px-4 py-2 text-sm font-medium text-background"
              data-testid="create-submit"
            >
              Create
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div data-testid="portfolio-loading">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="mb-3 h-20 animate-pulse rounded-lg bg-gray-100 dark:bg-gray-800" />
          ))}
        </div>
      ) : portfolios.length === 0 ? (
        <div className="rounded-lg border border-foreground/10 p-8 text-center text-foreground/60">
          No portfolios yet. Create one to get started.
        </div>
      ) : (
        <div className="space-y-3">
          {portfolios.map((p) => (
            <div
              key={p.id}
              className="flex items-center justify-between rounded-lg border border-foreground/10 p-4 transition-colors hover:bg-foreground/5"
              data-testid={`portfolio-${p.id}`}
            >
              <Link href={`/portfolio/${p.id}`} className="flex-1">
                <div className="flex items-center gap-3">
                  <h2 className="font-semibold">{p.name}</h2>
                  <span className="rounded-full bg-foreground/10 px-2 py-0.5 text-xs">
                    {p.mode}
                  </span>
                </div>
                <p className="mt-1 text-sm text-foreground/60">
                  {p.holdings_count} holding{p.holdings_count !== 1 ? "s" : ""} · Created {formatDate(p.created_at)}
                </p>
              </Link>
              <button
                onClick={(e) => { e.preventDefault(); handleDelete(p.id); }}
                className="ml-4 text-sm text-red-500 hover:text-red-700"
                data-testid={`delete-${p.id}`}
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </main>
  );
}
