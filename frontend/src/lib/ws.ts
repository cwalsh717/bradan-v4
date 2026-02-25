"use client";

import { useEffect, useRef, useState } from "react";

import { API_BASE } from "@/lib/api";

function httpToWs(url: string): string {
  return url.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
}

export interface UseWebSocketResult<T> {
  data: T | null;
  isConnected: boolean;
}

export function useWebSocket<T = unknown>(
  path: string,
  options?: { enabled?: boolean },
): UseWebSocketResult<T> {
  const enabled = options?.enabled ?? true;

  const [data, setData] = useState<T | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!enabled) {
      return;
    }

    const wsUrl = `${httpToWs(API_BASE)}${path}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.addEventListener("open", () => {
      setIsConnected(true);
    });

    ws.addEventListener("close", () => {
      setIsConnected(false);
    });

    ws.addEventListener("message", (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data as string) as T;
        setData(parsed);
      } catch {
        // ignore non-JSON messages
      }
    });

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [path, enabled]);

  return { data, isConnected };
}
