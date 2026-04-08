"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { tradingApi } from "@/lib/api";
import type { Order, OrderWsEvent } from "@/lib/types";

function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem("access_token");
  } catch {
    return null;
  }
}

interface UseOrdersWsOptions {
  /** Optional symbol filter. When set, only matching orders are kept. */
  symbol?: string;
  /** Disable the hook (e.g. when the modal is closed). */
  enabled?: boolean;
}

interface UseOrdersWsResult {
  openOrders: Order[];
  isConnected: boolean;
  refresh: () => void;
}

function wsUrlForOrders(token: string): string {
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1/orders/ws?token=${encodeURIComponent(token)}`;
}

function normaliseOrder(raw: unknown): Order | null {
  if (!raw || typeof raw !== "object") return null;
  const r = raw as Record<string, unknown>;
  if (typeof r.id !== "string") return null;
  return {
    id: String(r.id),
    symbol: String(r.symbol ?? ""),
    side: (r.side as Order["side"]) ?? "buy",
    order_type: (r.order_type as Order["order_type"]) ?? "market",
    status: (r.status as Order["status"]) ?? "pending",
    quantity: Number(r.quantity ?? 0),
    price: r.price != null ? Number(r.price) : undefined,
    filled_price: r.filled_price != null ? Number(r.filled_price) : undefined,
    fee: Number(r.fee ?? 0),
    created_at: String(r.created_at ?? new Date().toISOString()),
  };
}

/**
 * Subscribe to the per-user order WebSocket stream with an automatic fall back
 * to REST polling if the socket cannot be established or drops.
 */
export function useOrdersWs({
  symbol,
  enabled = true,
}: UseOrdersWsOptions = {}): UseOrdersWsResult {
  const [openOrders, setOpenOrders] = useState<Order[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const pollTimerRef = useRef<number | null>(null);
  const refreshKeyRef = useRef(0);
  const [refreshTick, setRefreshTick] = useState(0);

  const refresh = useCallback(() => {
    refreshKeyRef.current += 1;
    setRefreshTick((t) => t + 1);
  }, []);

  // Initial snapshot + polling fallback
  useEffect(() => {
    if (!enabled) {
      setOpenOrders([]);
      return;
    }
    let cancelled = false;

    const fetchOnce = async () => {
      try {
        const list = await tradingApi.getOpenOrders(symbol);
        if (!cancelled) setOpenOrders(list);
      } catch {
        // Ignore; WebSocket may still deliver data
      }
    };
    void fetchOnce();

    return () => {
      cancelled = true;
    };
  }, [enabled, symbol, refreshTick]);

  // WebSocket subscription
  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;

    const token = getAccessToken();
    if (!token) {
      // No token → polling every 5s
      const timer = window.setInterval(() => refresh(), 5000);
      pollTimerRef.current = timer;
      return () => {
        window.clearInterval(timer);
        pollTimerRef.current = null;
      };
    }

    let closed = false;
    let reconnectTimer: number | null = null;

    const connect = () => {
      try {
        const ws = new WebSocket(wsUrlForOrders(token));
        wsRef.current = ws;

        ws.onopen = () => {
          if (closed) return;
          setIsConnected(true);
          if (pollTimerRef.current) {
            window.clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        };

        ws.onmessage = (event: MessageEvent) => {
          try {
            const parsed = JSON.parse(event.data as string) as OrderWsEvent;
            if (parsed.event === "warning") return;

            const order = normaliseOrder(parsed.order);
            if (!order) return;
            if (symbol && order.symbol.toUpperCase() !== symbol.toUpperCase()) {
              return;
            }

            setOpenOrders((prev) => {
              const map = new Map(prev.map((o) => [o.id, o]));
              if (parsed.event === "order_done") {
                map.delete(order.id);
              } else {
                map.set(order.id, order);
              }
              return Array.from(map.values()).sort(
                (a, b) => (b.created_at || "").localeCompare(a.created_at || ""),
              );
            });
          } catch {
            // Malformed — ignore
          }
        };

        ws.onclose = () => {
          setIsConnected(false);
          if (closed) return;
          // Fall back to polling while we reconnect
          if (!pollTimerRef.current) {
            pollTimerRef.current = window.setInterval(() => refresh(), 5000);
          }
          reconnectTimer = window.setTimeout(connect, 3000);
        };

        ws.onerror = () => {
          // onclose will fire
        };
      } catch {
        // Fall back to polling immediately
        if (!pollTimerRef.current) {
          pollTimerRef.current = window.setInterval(() => refresh(), 5000);
        }
      }
    };

    connect();

    return () => {
      closed = true;
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          // ignore
        }
        wsRef.current = null;
      }
      if (reconnectTimer != null) {
        window.clearTimeout(reconnectTimer);
      }
      if (pollTimerRef.current) {
        window.clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
      setIsConnected(false);
    };
  }, [enabled, symbol, refresh]);

  return { openOrders, isConnected, refresh };
}
