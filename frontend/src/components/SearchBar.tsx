"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { apiGet } from "@/lib/api";
import type { SearchResult } from "@/lib/types";

export function SearchBar() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const search = useCallback(async (q: string) => {
    if (q.length < 2) {
      setResults([]);
      setIsOpen(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    try {
      const data = await apiGet<SearchResult[]>(
        `/api/search?q=${encodeURIComponent(q)}`,
      );
      setResults(data);
      setIsOpen(true);
    } catch {
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }

    if (query.length < 2) {
      setResults([]);
      setIsOpen(false);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    debounceRef.current = setTimeout(() => {
      search(query);
    }, 300);

    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, [query, search]);

  const selectResult = useCallback(
    (symbol: string) => {
      setQuery("");
      setResults([]);
      setIsOpen(false);
      setActiveIndex(-1);
      router.push(`/stocks/${symbol}`);
    },
    [router],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isOpen) return;

      switch (e.key) {
        case "ArrowDown":
          e.preventDefault();
          setActiveIndex((prev) =>
            prev < results.length - 1 ? prev + 1 : prev,
          );
          break;
        case "ArrowUp":
          e.preventDefault();
          setActiveIndex((prev) => (prev > 0 ? prev - 1 : -1));
          break;
        case "Enter":
          e.preventDefault();
          if (activeIndex >= 0 && activeIndex < results.length) {
            selectResult(results[activeIndex].symbol);
          }
          break;
        case "Escape":
          setIsOpen(false);
          setActiveIndex(-1);
          inputRef.current?.blur();
          break;
      }
    },
    [isOpen, activeIndex, results, selectResult],
  );

  const handleBlur = useCallback(() => {
    // Small delay to allow click events on dropdown items to register
    setTimeout(() => {
      setIsOpen(false);
      setActiveIndex(-1);
    }, 200);
  }, []);

  return (
    <div ref={containerRef} className="relative">
      <div className="relative">
        <svg
          className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/40"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z"
          />
        </svg>
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
          onFocus={() => {
            if (results.length > 0 && query.length >= 2) {
              setIsOpen(true);
            }
          }}
          placeholder="Search stocks..."
          className="h-8 w-56 rounded-md border border-foreground/20 bg-background pl-8 pr-3 text-sm text-foreground placeholder:text-foreground/40 focus:border-foreground/40 focus:outline-none"
          aria-label="Search stocks"
          role="combobox"
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-activedescendant={
            activeIndex >= 0 ? `search-result-${activeIndex}` : undefined
          }
        />
      </div>

      {isOpen && (
        <ul
          role="listbox"
          className="absolute left-0 top-full z-50 mt-1 max-h-64 w-72 overflow-auto rounded-md border border-foreground/20 bg-background shadow-lg"
        >
          {isLoading && (
            <li className="px-3 py-2 text-sm text-foreground/60">
              Searching...
            </li>
          )}
          {!isLoading && results.length === 0 && (
            <li className="px-3 py-2 text-sm text-foreground/60">
              No results
            </li>
          )}
          {!isLoading &&
            results.map((result, index) => (
              <li
                key={result.symbol}
                id={`search-result-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                className={`flex cursor-pointer items-center gap-2 px-3 py-2 text-sm ${
                  index === activeIndex
                    ? "bg-foreground/10"
                    : "hover:bg-foreground/5"
                }`}
                onMouseDown={(e) => {
                  e.preventDefault();
                  selectResult(result.symbol);
                }}
                onMouseEnter={() => setActiveIndex(index)}
              >
                <span className="font-bold text-foreground">
                  {result.symbol}
                </span>
                <span className="truncate text-foreground/60">
                  {result.name}
                </span>
                <span className="ml-auto text-xs text-foreground/40">
                  {result.exchange}
                </span>
                {result.cached && (
                  <span
                    className="h-2 w-2 flex-shrink-0 rounded-full bg-green-500"
                    title="Cached"
                    aria-label="Cached"
                  />
                )}
              </li>
            ))}
        </ul>
      )}
    </div>
  );
}
