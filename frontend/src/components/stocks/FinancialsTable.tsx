"use client";

import { formatLargeNumber } from "@/lib/format";
import type { FinancialStatement } from "@/lib/types";

interface FinancialsTableProps {
  statements: FinancialStatement[];
}

const METRICS: { key: string; label: string }[] = [
  { key: "revenue", label: "Revenue" },
  { key: "gross_profit", label: "Gross Profit" },
  { key: "operating_income", label: "Operating Income" },
  { key: "net_income", label: "Net Income" },
];

export function FinancialsTable({ statements }: FinancialsTableProps) {
  if (!statements.length) {
    return (
      <p className="py-8 text-center text-foreground/50">
        No financial data available
      </p>
    );
  }

  // Sort by fiscal_date descending and take at most 5
  const sorted = [...statements]
    .sort(
      (a, b) =>
        new Date(b.fiscal_date).getTime() - new Date(a.fiscal_date).getTime(),
    )
    .slice(0, 5);

  // Filter to income_statement type if available
  const incomeStatements = sorted.filter(
    (s) => s.statement_type === "income_statement",
  );
  const display = incomeStatements.length > 0 ? incomeStatements : sorted;

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-foreground/10">
            <th className="py-3 pr-4 text-left font-medium text-foreground/60">
              Metric
            </th>
            {display.map((s) => (
              <th
                key={s.fiscal_date}
                className="px-4 py-3 text-right font-medium text-foreground/60"
              >
                {new Date(s.fiscal_date).getFullYear()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => (
            <tr
              key={metric.key}
              className="border-b border-foreground/5 hover:bg-foreground/5"
            >
              <td className="py-3 pr-4 font-medium">{metric.label}</td>
              {display.map((s) => (
                <td
                  key={s.fiscal_date}
                  className="px-4 py-3 text-right tabular-nums"
                >
                  {formatLargeNumber(s.data?.[metric.key] ?? null)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
