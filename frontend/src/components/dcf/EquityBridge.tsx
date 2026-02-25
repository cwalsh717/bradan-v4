"use client";

import { EquityBridge as EquityBridgeType } from "@/lib/types";
import { formatLargeNumber, formatCurrency } from "@/lib/format";

interface EquityBridgeProps {
  bridge: EquityBridgeType;
}

interface BridgeStep {
  label: string;
  value: number;
  sign: "+" | "-" | "=" | "";
  isFinal?: boolean;
}

export function EquityBridge({ bridge }: EquityBridgeProps) {
  const steps: BridgeStep[] = [
    { label: "Enterprise Value", value: bridge.enterprise_value, sign: "" },
    { label: "Cash", value: bridge.plus_cash, sign: "+" },
    { label: "Debt", value: bridge.minus_debt, sign: "-" },
    { label: "Minority Interests", value: bridge.minus_minority_interests, sign: "-" },
    { label: "Preferred Stock", value: bridge.minus_preferred_stock, sign: "-" },
    { label: "Equity Value", value: bridge.equity_value, sign: "=" },
  ];

  return (
    <div data-testid="equity-bridge">
      <h3 className="mb-3 text-sm font-semibold text-foreground/70 uppercase tracking-wide">
        Equity Bridge
      </h3>
      <div className="flex flex-wrap items-center gap-2">
        {steps.map((step, idx) => (
          <div key={step.label} className="flex items-center gap-2">
            {step.sign && (
              <span className="text-lg font-bold text-foreground/50">
                {step.sign}
              </span>
            )}
            <div
              className={`rounded-lg border px-4 py-3 text-center ${
                step.sign === "="
                  ? "border-blue-500 bg-blue-50"
                  : "border-foreground/10 bg-background"
              }`}
            >
              <p className="text-xs text-foreground/60">{step.label}</p>
              <p className="text-sm font-semibold">
                {formatLargeNumber(step.value)}
              </p>
            </div>
            {idx < steps.length - 1 && !steps[idx + 1].sign && (
              <span className="text-foreground/30">&rarr;</span>
            )}
          </div>
        ))}
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-foreground/50">&divide;</span>
          <div className="rounded-lg border border-foreground/10 bg-background px-4 py-3 text-center">
            <p className="text-xs text-foreground/60">Shares</p>
            <p className="text-sm font-semibold">
              {formatLargeNumber(bridge.shares_outstanding)}
            </p>
          </div>
          <span className="text-lg font-bold text-foreground/50">=</span>
          <div className="rounded-lg border border-green-500 bg-green-50 px-4 py-3 text-center">
            <p className="text-xs text-foreground/60">Value/Share</p>
            <p className="text-sm font-bold text-green-700">
              {formatCurrency(bridge.value_per_share)}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
