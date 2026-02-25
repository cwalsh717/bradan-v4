"use client";

import { YearProjection, TerminalValue } from "@/lib/types";
import {
  formatLargeNumber,
  formatPercent,
  formatRatio,
} from "@/lib/format";

interface ProjectionTableProps {
  projections: YearProjection[];
  terminal: TerminalValue;
}

export function ProjectionTable({ projections, terminal }: ProjectionTableProps) {
  return (
    <div data-testid="projection-table" className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-foreground/10 text-left text-xs text-foreground/60 uppercase tracking-wide">
            <th className="px-3 py-2">Year</th>
            <th className="px-3 py-2">Growth</th>
            <th className="px-3 py-2">Revenue</th>
            <th className="px-3 py-2">EBIT</th>
            <th className="px-3 py-2">FCFF</th>
            <th className="px-3 py-2">WACC</th>
            <th className="px-3 py-2">PV(FCFF)</th>
            <th className="px-3 py-2">Beta</th>
          </tr>
        </thead>
        <tbody>
          {projections.map((row) => (
            <tr
              key={row.year}
              className="border-b border-foreground/5 hover:bg-foreground/[0.02]"
            >
              <td className="px-3 py-2 font-medium">{row.year}</td>
              <td className="px-3 py-2">{formatPercent(row.growth_rate * 100)}</td>
              <td className="px-3 py-2">{formatLargeNumber(row.revenue)}</td>
              <td className="px-3 py-2">{formatLargeNumber(row.ebit)}</td>
              <td className="px-3 py-2">{formatLargeNumber(row.fcff)}</td>
              <td className="px-3 py-2">{formatPercent(row.wacc * 100)}</td>
              <td className="px-3 py-2">{formatLargeNumber(row.pv_fcff)}</td>
              <td className="px-3 py-2">{formatRatio(row.beta)}</td>
            </tr>
          ))}
          {/* Terminal year summary row */}
          <tr className="border-t-2 border-foreground/20 bg-foreground/[0.03] font-semibold">
            <td className="px-3 py-2">Terminal</td>
            <td className="px-3 py-2">{formatPercent(terminal.terminal_growth * 100)}</td>
            <td className="px-3 py-2" colSpan={2}></td>
            <td className="px-3 py-2">{formatLargeNumber(terminal.terminal_fcff)}</td>
            <td className="px-3 py-2">{formatPercent(terminal.terminal_wacc * 100)}</td>
            <td className="px-3 py-2">{formatLargeNumber(terminal.pv_terminal)}</td>
            <td className="px-3 py-2"></td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
