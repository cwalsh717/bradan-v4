import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useWebSocket } from "../ws";

class MockWebSocket {
  static instances: MockWebSocket[] = [];
  url: string;
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  close = vi.fn();
  listeners: Record<string, Array<(ev: unknown) => void>> = {};

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  addEventListener(event: string, cb: (ev: unknown) => void) {
    if (!this.listeners[event]) {
      this.listeners[event] = [];
    }
    this.listeners[event].push(cb);
  }

  removeEventListener(event: string, cb: (ev: unknown) => void) {
    if (this.listeners[event]) {
      this.listeners[event] = this.listeners[event].filter((l) => l !== cb);
    }
  }

  simulateOpen() {
    this.listeners["open"]?.forEach((cb) => cb(new Event("open")));
  }

  simulateMessage(data: unknown) {
    this.listeners["message"]?.forEach((cb) =>
      cb(new MessageEvent("message", { data: JSON.stringify(data) })),
    );
  }

  simulateClose() {
    this.listeners["close"]?.forEach((cb) =>
      cb(new CloseEvent("close")),
    );
  }
}

const OriginalWebSocket = globalThis.WebSocket;

beforeEach(() => {
  MockWebSocket.instances = [];
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  globalThis.WebSocket = MockWebSocket as any;
});

afterEach(() => {
  globalThis.WebSocket = OriginalWebSocket;
});

describe("useWebSocket", () => {
  it("returns initial state (data: null, isConnected: false)", () => {
    const { result } = renderHook(() =>
      useWebSocket("/ws/prices", { enabled: false }),
    );

    expect(result.current.data).toBeNull();
    expect(result.current.isConnected).toBe(false);
  });

  it("connects when enabled (default)", () => {
    renderHook(() => useWebSocket("/ws/prices"));

    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe("ws://localhost:8000/ws/prices");
  });

  it("does not connect when enabled is false", () => {
    renderHook(() =>
      useWebSocket("/ws/prices", { enabled: false }),
    );

    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it("updates isConnected on open/close", () => {
    const { result } = renderHook(() => useWebSocket("/ws/prices"));
    const ws = MockWebSocket.instances[0];

    expect(result.current.isConnected).toBe(false);

    act(() => {
      ws.simulateOpen();
    });
    expect(result.current.isConnected).toBe(true);

    act(() => {
      ws.simulateClose();
    });
    expect(result.current.isConnected).toBe(false);
  });

  it("parses incoming JSON messages into data", () => {
    const { result } = renderHook(() => useWebSocket("/ws/prices"));
    const ws = MockWebSocket.instances[0];

    act(() => {
      ws.simulateOpen();
      ws.simulateMessage({ symbol: "AAPL", price: 150.0 });
    });

    expect(result.current.data).toEqual({ symbol: "AAPL", price: 150.0 });
  });

  it("cleans up on unmount", () => {
    const { unmount } = renderHook(() => useWebSocket("/ws/prices"));
    const ws = MockWebSocket.instances[0];

    unmount();

    expect(ws.close).toHaveBeenCalled();
  });
});
