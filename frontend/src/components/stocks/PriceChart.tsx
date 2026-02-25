"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface PriceDataPoint {
  date: string;
  close: number;
}

interface PriceChartProps {
  data: PriceDataPoint[];
  height?: number;
}

function formatChartDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatChartPrice(value: number): string {
  return `$${value.toFixed(2)}`;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}

function ChartTooltip({ active, payload, label }: ChartTooltipProps) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-foreground/20 bg-background px-3 py-2 text-sm shadow-md">
      <p className="text-foreground/60">{label}</p>
      <p className="font-semibold text-foreground">
        ${payload[0].value.toFixed(2)}
      </p>
    </div>
  );
}

export function PriceChart({ data, height = 300 }: PriceChartProps) {
  if (!data.length) {
    return (
      <div
        className="flex items-center justify-center text-foreground/50"
        style={{ height }}
      >
        No price data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
        <defs>
          <linearGradient id="priceGradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
          </linearGradient>
        </defs>
        <XAxis
          dataKey="date"
          tickFormatter={formatChartDate}
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          minTickGap={40}
        />
        <YAxis
          tickFormatter={formatChartPrice}
          tick={{ fontSize: 12 }}
          tickLine={false}
          axisLine={false}
          domain={["auto", "auto"]}
          width={70}
        />
        <Tooltip content={<ChartTooltip />} />
        <Area
          type="monotone"
          dataKey="close"
          stroke="#3b82f6"
          fill="url(#priceGradient)"
          strokeWidth={2}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
