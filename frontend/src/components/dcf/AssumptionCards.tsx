"use client";

import { DCFResult } from "@/lib/types";
import { formatPercent, formatRatio } from "@/lib/format";
import { GlossaryTooltip } from "@/components/GlossaryTooltip";

interface AssumptionCardsProps {
  result: DCFResult;
}

interface CardData {
  glossaryTerm: string;
  label: string;
  value: string;
}

export function AssumptionCards({ result }: AssumptionCardsProps) {
  const { computed_inputs, terminal } = result;

  const cards: CardData[] = [
    {
      glossaryTerm: "wacc",
      label: "Cost of Running the Business",
      value: formatPercent(computed_inputs.wacc * 100),
    },
    {
      glossaryTerm: "beta",
      label: "Risk Level",
      value: formatRatio(computed_inputs.levered_beta),
    },
    {
      glossaryTerm: "terminal_growth",
      label: "Long-Term Growth",
      value: formatPercent(terminal.terminal_growth * 100),
    },
    {
      glossaryTerm: "cost_of_equity",
      label: "Expected Growth",
      value: formatPercent(computed_inputs.expected_growth * 100),
    },
    {
      glossaryTerm: "cost_of_debt",
      label: "Effective Tax Rate",
      value: formatPercent(computed_inputs.effective_tax_rate * 100),
    },
  ];

  return (
    <div data-testid="assumption-cards" className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
      {cards.map((card) => (
        <div
          key={card.glossaryTerm}
          className="rounded-lg border border-foreground/10 bg-background p-4 shadow-sm"
        >
          <p className="text-sm text-foreground/60">
            <GlossaryTooltip term={card.glossaryTerm}>
              {card.label}
            </GlossaryTooltip>
          </p>
          <p className="mt-1 text-xl font-semibold">{card.value}</p>
        </div>
      ))}
    </div>
  );
}
