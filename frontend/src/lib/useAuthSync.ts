"use client";

import { useEffect, useRef } from "react";
import { useAuth } from "@clerk/nextjs";
import { authFetch } from "@/lib/api";

/**
 * Syncs the Clerk user to the backend on first load.
 * Call this once from the portfolio layout or page.
 */
export function useAuthSync() {
  const { getToken, isSignedIn } = useAuth();
  const synced = useRef(false);

  useEffect(() => {
    if (!isSignedIn || synced.current) return;
    synced.current = true;

    getToken().then((token) => {
      if (token) {
        authFetch("/api/auth/sync", token, { method: "POST" }).catch(() => {
          // Sync failure is non-fatal — user may already exist
        });
      }
    });
  }, [isSignedIn, getToken]);
}
