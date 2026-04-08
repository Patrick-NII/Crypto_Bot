"use client";

import { useEffect, useState } from "react";
import { tradingApi } from "@/lib/api";
import type { OrderPreflight, OrderSide } from "@/lib/types";

interface UsePreflightParams {
  symbol: string | null;
  side: OrderSide;
  quantity: number;
  referencePrice?: number;
  /** Set to ``false`` to pause the hook while the user is still typing. */
  enabled?: boolean;
  /** Debounce window in ms. Default 300ms. */
  debounceMs?: number;
}

interface UsePreflightResult {
  preflight: OrderPreflight | null;
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Debounced preflight hook. Calls ``GET /orders/preflight`` whenever the
 * inputs change and returns the latest response alongside loading/error
 * state. Automatically cancels in-flight requests on unmount.
 */
export function usePreflight({
  symbol,
  side,
  quantity,
  referencePrice,
  enabled = true,
  debounceMs = 300,
}: UsePreflightParams): UsePreflightResult {
  const [preflight, setPreflight] = useState<OrderPreflight | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    if (!enabled || !symbol || !(quantity > 0)) {
      setPreflight(null);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      setLoading(true);
      setError(null);
      tradingApi
        .preflightOrder({
          symbol,
          side,
          quantity,
          reference_price: referencePrice,
        })
        .then((result) => {
          if (cancelled) return;
          setPreflight(result);
        })
        .catch((err) => {
          if (cancelled) return;
          setPreflight(null);
          const message =
            err instanceof Error
              ? err.message
              : "Impossible de verifier l'ordre pour le moment.";
          setError(message);
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    }, debounceMs);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [symbol, side, quantity, referencePrice, enabled, debounceMs, refreshKey]);

  return {
    preflight,
    loading,
    error,
    refresh: () => setRefreshKey((k) => k + 1),
  };
}
