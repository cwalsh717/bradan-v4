"use client";

import { DCFResult } from "@/lib/types";
import { formatCurrency, formatPercent, changeColor } from "@/lib/format";

interface HeadlineProps {
  result: DCFResult;
}

function verdictBadge(verdict: string) {
  const lower = verdict.toLowerCase();
  if (lower.includes("under")) {
    return (
      <span className="inline-block rounded-full bg-green-100 px-3 py-1 text-sm font-semibold text-green-800">
        Undervalued
      </span>
    );
  }
  if (lower.includes("over")) {
    return (
      <span className="inline-block rounded-full bg-red-100 px-3 py-1 text-sm font-semibold text-red-800">
        Overvalued
      </span>
    );
  }
  return (
    <span className="inline-block rounded-full bg-gray-100 px-3 py-1 text-sm font-semibold text-gray-700">
      Fairly Valued
    </span>
  );
}

export function Headline({ result }: HeadlineProps) {
  const upsideColor = changeColor(result.implied_upside);

  return (
    <div data-testid="dcf-headline">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">
          {result.company_name}{" "}
          <span className="text-foreground/60">({result.symbol})</span>
        </h1>
        {verdictBadge(result.verdict)}
      </div>

      <div className="mt-4 flex flex-wrap items-end gap-8">
        <div>
          <p className="text-sm text-foreground/60">Intrinsic Value</p>
          <p className="text-4xl font-bold" data-testid="value-per-share">
            {formatCurrency(result.value_per_share)}
          </p>
        </div>
        <div>
          <p className="text-sm text-foreground/60">Current Price</p>
          <p className="text-2xl font-semibold text-foreground/80">
            {formatCurrency(result.current_price)}
          </p>
        </div>
        <div>
          <p className="text-sm text-foreground/60">Implied Upside</p>
          <p className={`text-2xl font-semibold ${upsideColor}`} data-testid="implied-upside">
            {result.implied_upside > 0 ? "+" : ""}
            {formatPercent(result.implied_upside)}
          </p>
        </div>
      </div>

      <p className="mt-3 text-xs text-foreground/50">
        Based on fiscal data as of {result.source_fiscal_date} | Computed{" "}
        {result.computed_at}
      </p>
    </div>
  );
}
