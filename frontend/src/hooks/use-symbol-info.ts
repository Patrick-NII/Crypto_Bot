"use client";

import { useEffect, useState } from "react";
import { tradingApi } from "@/lib/api";
import type { SymbolInfo } from "@/lib/types";

/** Module-level cache keyed by normalised symbol with a 30 min TTL. */
const CACHE_TTL_MS = 30 * 60 * 1000;
const cache = new Map<string, { ts: number; info: SymbolInfo }>();

function readCache(symbol: string): SymbolInfo | null {
  const entry = cache.get(symbol);
  if (!entry) return null;
  if (Date.now() - entry.ts > CACHE_TTL_MS) {
    cache.delete(symbol);
    return null;
  }
  return entry.info;
}

function writeCache(symbol: string, info: SymbolInfo): void {
  cache.set(symbol, { ts: Date.now(), info });
}

interface UseSymbolInfoResult {
  info: SymbolInfo | null;
  loading: boolean;
  error: Error | null;
}

/**
 * Fetch Binance exchange filters (stepSize, tickSize, minNotional, etc.)
 * for a trading pair. The result is cached in-memory for 30 minutes.
 *
 * The frontend uses these filters to validate user input BEFORE submission,
 * preventing the late-error class where Binance rejects an order because the
 * amount violates LOT_SIZE or MIN_NOTIONAL.
 */
export function useSymbolInfo(symbol: string | null): UseSymbolInfoResult {
  const normalized = symbol
    ? symbol.includes("/")
      ? symbol.toUpperCase()
      : `${symbol.toUpperCase()}/USDT`
    : null;

  const [info, setInfo] = useState<SymbolInfo | null>(
    normalized ? readCache(normalized) : null,
  );
  const [loading, setLoading] = useState(!info && normalized !== null);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!normalized) {
      setInfo(null);
      setLoading(false);
      setError(null);
      return;
    }

    // Serve cache immediately if available
    const cached = readCache(normalized);
    if (cached) {
      setInfo(cached);
      setLoading(false);
      setError(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    setError(null);

    tradingApi
      .getSymbolInfo(normalized)
      .then((result) => {
        if (cancelled) return;
        writeCache(normalized, result);
        setInfo(result);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [normalized]);

  return { info, loading, error };
}
