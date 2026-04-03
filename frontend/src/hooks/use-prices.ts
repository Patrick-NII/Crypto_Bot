"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { pricesApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import type { CryptoPrice } from "@/lib/types";

interface UsePricesResult {
  prices: Record<string, CryptoPrice>;
  loading: boolean;
  error: Error | null;
}

/**
 * React hook that fetches initial crypto prices via REST and subscribes
 * to live WebSocket updates for the given symbols.
 */
export function usePrices(symbols: string[]): UsePricesResult {
  const [prices, setPrices] = useState<Record<string, CryptoPrice>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  // Keep a stable reference so that effects can compare without
  // triggering infinite re-renders.
  const symbolsKey = symbols
    .map((s) => s.toUpperCase())
    .sort()
    .join(",");

  // Fetch initial prices via REST
  const fetchInitial = useCallback(async () => {
    if (symbols.length === 0) {
      setPrices({});
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const data = await pricesApi.getCrypto();
      const map: Record<string, CryptoPrice> = {};
      for (const item of data) {
        if (symbols.some((s) => s.toUpperCase() === item.symbol.toUpperCase())) {
          map[item.symbol.toUpperCase()] = item;
        }
      }
      setPrices(map);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey]);

  useEffect(() => {
    fetchInitial();
  }, [fetchInitial]);

  // Subscribe to live WebSocket updates
  const unsubsRef = useRef<(() => void)[]>([]);

  useEffect(() => {
    // Clean up previous subscriptions
    for (const unsub of unsubsRef.current) {
      unsub();
    }
    unsubsRef.current = [];

    if (symbols.length === 0) return;

    for (const symbol of symbols) {
      const unsub = priceWs.subscribe(symbol, (data: CryptoPrice) => {
        setPrices((prev) => ({
          ...prev,
          [data.symbol.toUpperCase()]: data,
        }));
      });
      unsubsRef.current.push(unsub);
    }

    return () => {
      for (const unsub of unsubsRef.current) {
        unsub();
      }
      unsubsRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsKey]);

  return { prices, loading, error };
}
