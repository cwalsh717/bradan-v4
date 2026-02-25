"use client";

import { SensitivityMatrix } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";

interface SensitivityTableProps {
  matrix: SensitivityMatrix;
  currentPrice: number;
}

export function SensitivityTable({ matrix, currentPrice }: SensitivityTableProps) {
  return (
    <div data-testid="sensitivity-table" className="overflow-x-auto">
      <h3 className="mb-3 text-sm font-semibold text-foreground/70 uppercase tracking-wide">
        Sensitivity Analysis (WACC vs Growth)
      </h3>
      <table className="min-w-full text-sm">
        <thead>
          <tr>
            <th className="px-3 py-2 text-left text-xs text-foreground/60">
              Growth \ WACC
            </th>
            {matrix.wacc_values.map((wacc) => (
              <th
                key={wacc}
                className={`px-3 py-2 text-center text-xs ${
                  wacc === matrix.base_wacc
                    ? "font-bold text-blue-600"
                    : "text-foreground/60"
                }`}
              >
                {formatPercent(wacc * 100)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {matrix.growth_values.map((growth, rowIdx) => (
            <tr key={growth} className="border-b border-foreground/5">
              <td
                className={`px-3 py-2 text-xs ${
                  growth === matrix.base_growth
                    ? "font-bold text-blue-600"
                    : "text-foreground/60"
                }`}
              >
                {formatPercent(growth * 100)}
              </td>
              {matrix.wacc_values.map((wacc, colIdx) => {
                const value = matrix.matrix[rowIdx][colIdx];
                const isBase =
                  wacc === matrix.base_wacc && growth === matrix.base_growth;
                const abovePrice = value >= currentPrice;

                let cellClass = abovePrice
                  ? "bg-green-50 text-green-800"
                  : "bg-red-50 text-red-800";

                if (isBase) {
                  cellClass += " ring-2 ring-blue-500 font-bold";
                }

                return (
                  <td
                    key={`${growth}-${wacc}`}
                    className={`px-3 py-2 text-center text-xs ${cellClass}`}
                    data-testid={isBase ? "base-case-cell" : undefined}
                  >
                    {formatCurrency(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
