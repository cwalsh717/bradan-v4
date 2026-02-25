"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { getGlossaryEntry } from "@/lib/glossary";

interface GlossaryTooltipProps {
  term: string;
  children?: React.ReactNode;
}

export function GlossaryTooltip({ term, children }: GlossaryTooltipProps) {
  const entry = getGlossaryEntry(term);
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState<"above" | "below">("above");
  const triggerRef = useRef<HTMLSpanElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const updatePosition = useCallback(() => {
    if (!triggerRef.current) return;
    const rect = triggerRef.current.getBoundingClientRect();
    // If there's less than 100px above the trigger, flip to below
    setPosition(rect.top < 100 ? "below" : "above");
  }, []);

  useEffect(() => {
    if (isVisible) {
      updatePosition();
    }
  }, [isVisible, updatePosition]);

  // If term is not found, just render children or the raw term
  if (!entry) {
    return <span>{children ?? term}</span>;
  }

  const label = children ?? entry.technical_label;

  return (
    <span
      ref={triggerRef}
      className="relative inline-block cursor-help border-b border-dotted border-foreground/40"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
      tabIndex={0}
      role="button"
      aria-describedby={isVisible ? `glossary-tooltip-${term}` : undefined}
    >
      {label}
      {isVisible && (
        <div
          ref={tooltipRef}
          id={`glossary-tooltip-${term}`}
          role="tooltip"
          className={`absolute left-1/2 z-50 w-64 -translate-x-1/2 rounded-md border border-foreground/20 bg-background px-3 py-2 shadow-lg ${
            position === "above" ? "bottom-full mb-2" : "top-full mt-2"
          }`}
        >
          <p className="text-sm font-semibold text-foreground">
            {entry.display_label}
          </p>
          <p className="mt-1 text-xs leading-relaxed text-foreground/70">
            {entry.tooltip}
          </p>
        </div>
      )}
    </span>
  );
}
