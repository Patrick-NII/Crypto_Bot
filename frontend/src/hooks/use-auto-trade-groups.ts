"use client";

import { useEffect, useState } from "react";
import { aiApi } from "@/lib/api";
import type { TradeGroup } from "@/lib/types";

interface UseAutoTradeGroupsOptions {
  enabled?: boolean;
  status?: "open" | "closed" | "cancelled";
  limit?: number;
  pollMs?: number;
}

interface UseAutoTradeGroupsResult {
  groups: TradeGroup[];
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

/** Poll the auto-trader trade groups (position lifecycles). */
export function useAutoTradeGroups({
  enabled = true,
  status,
  limit = 50,
  pollMs = 10000,
}: UseAutoTradeGroupsOptions = {}): UseAutoTradeGroupsResult {
  const [groups, setGroups] = useState<TradeGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const fetchOnce = async () => {
      setLoading(true);
      try {
        const result = await aiApi.getAutoTradeGroups({ status, limit });
        if (cancelled) return;
        setGroups((result.trade_groups || []) as unknown as TradeGroup[]);
        setError(null);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    void fetchOnce();
    const interval = window.setInterval(() => void fetchOnce(), pollMs);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [enabled, status, limit, pollMs, refreshTick]);

  return {
    groups,
    loading,
    error,
    refresh: () => setRefreshTick((t) => t + 1),
  };
}
