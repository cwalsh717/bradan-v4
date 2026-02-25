"use client";

interface ScenarioSelectorProps {
  activeScenario: string;
  onSelect: (scenario: string) => void;
}

const scenarios = [
  { key: "conservative", label: "Conservative" },
  { key: "moderate", label: "Moderate" },
  { key: "optimistic", label: "Optimistic" },
];

export function ScenarioSelector({
  activeScenario,
  onSelect,
}: ScenarioSelectorProps) {
  return (
    <div data-testid="scenario-selector" className="flex gap-2">
      {scenarios.map(({ key, label }) => {
        const isActive = activeScenario === key;
        return (
          <button
            key={key}
            onClick={() => onSelect(key)}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              isActive
                ? "bg-blue-600 text-white"
                : "border border-foreground/20 bg-background text-foreground hover:bg-foreground/5"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
