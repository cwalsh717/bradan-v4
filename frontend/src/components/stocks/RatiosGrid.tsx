"use client";

import { formatRatio, formatPercent } from "@/lib/format";
import { GlossaryTooltip } from "@/components/GlossaryTooltip";
import type { FinancialRatios } from "@/lib/types";

interface RatiosGridProps {
  ratios: FinancialRatios;
}

interface RatioItem {
  key: keyof FinancialRatios;
  label: string;
  glossaryTerm?: string;
  isPercent?: boolean;
}

interface RatioGroup {
  title: string;
  items: RatioItem[];
}

const RATIO_GROUPS: RatioGroup[] = [
  {
    title: "Profitability",
    items: [
      { key: "gross_margin", label: "Gross Margin", glossaryTerm: "gross_margin", isPercent: true },
      { key: "operating_margin", label: "Operating Margin", glossaryTerm: "operating_margin", isPercent: true },
      { key: "net_margin", label: "Net Margin", glossaryTerm: "net_margin", isPercent: true },
      { key: "roe", label: "ROE", glossaryTerm: "roe", isPercent: true },
      { key: "roa", label: "ROA", glossaryTerm: "roa", isPercent: true },
      { key: "roic", label: "ROIC", isPercent: true },
    ],
  },
  {
    title: "Liquidity",
    items: [
      { key: "current_ratio", label: "Current Ratio", glossaryTerm: "current_ratio" },
      { key: "quick_ratio", label: "Quick Ratio" },
      { key: "asset_turnover", label: "Asset Turnover" },
      { key: "inventory_turnover", label: "Inventory Turnover" },
    ],
  },
  {
    title: "Leverage",
    items: [
      { key: "debt_to_equity", label: "D/E", glossaryTerm: "debt_to_equity" },
      { key: "debt_to_assets", label: "Debt/Assets" },
      { key: "interest_coverage", label: "Interest Coverage" },
    ],
  },
  {
    title: "Valuation",
    items: [
      { key: "pe_ratio", label: "P/E", glossaryTerm: "pe_ratio" },
      { key: "pb_ratio", label: "P/B", glossaryTerm: "pb_ratio" },
      { key: "ps_ratio", label: "P/S" },
      { key: "ev_to_ebitda", label: "EV/EBITDA" },
    ],
  },
];

function formatValue(value: number | null, isPercent?: boolean): string {
  if (isPercent) return formatPercent(value);
  return formatRatio(value);
}

export function RatiosGrid({ ratios }: RatiosGridProps) {
  return (
    <div className="space-y-6">
      {RATIO_GROUPS.map((group) => (
        <div key={group.title}>
          <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-foreground/60">
            {group.title}
          </h3>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {group.items.map((item) => (
              <div
                key={item.key}
                className="rounded-lg border border-foreground/10 px-4 py-3"
              >
                <p className="text-xs text-foreground/60">
                  {item.glossaryTerm ? (
                    <GlossaryTooltip term={item.glossaryTerm}>
                      {item.label}
                    </GlossaryTooltip>
                  ) : (
                    item.label
                  )}
                </p>
                <p className="mt-1 text-lg font-semibold tabular-nums" data-testid={`ratio-${item.key}`}>
                  {formatValue(ratios[item.key], item.isPercent)}
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
