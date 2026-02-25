"use client";

import { useAuthSync } from "@/lib/useAuthSync";

export default function PortfolioLayout({ children }: { children: React.ReactNode }) {
  useAuthSync();
  return <>{children}</>;
}
