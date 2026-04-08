"use client";

import { useEffect, useState } from "react";
import { aiApi } from "@/lib/api";
import type { AutoDecision } from "@/lib/types";

interface UseAutoDecisionsOptions {
  enabled?: boolean;
  cycleId?: string;
  outcome?: string;
  limit?: number;
  pollMs?: number;
}

interface UseAutoDecisionsResult {
  decisions: AutoDecision[];
  loading: boolean;
  error: Error | null;
  refresh: () => void;
}

/**
 * Poll the auto-trading decision log.
 *
 * V1 uses plain polling every ``pollMs`` ms. When the panel is closed
 * (``enabled=false``), the hook stops polling and returns the last
 * snapshot.
 */
export function useAutoDecisions({
  enabled = true,
  cycleId,
  outcome,
  limit = 50,
  pollMs = 5000,
}: UseAutoDecisionsOptions = {}): UseAutoDecisionsResult {
  const [decisions, setDecisions] = useState<AutoDecision[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [refreshTick, setRefreshTick] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;

    const fetchOnce = async () => {
      setLoading(true);
      try {
        const result = await aiApi.getAutoDecisions({ cycle_id: cycleId, outcome, limit });
        if (cancelled) return;
        const parsed = (result.decisions || []).map((raw) => {
          const d = raw as unknown as AutoDecision;
          return {
            ...d,
            confidence: Number(d.confidence ?? 0),
            score: Number(d.score ?? 0),
          };
        });
        setDecisions(parsed);
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
  }, [enabled, cycleId, outcome, limit, pollMs, refreshTick]);

  return {
    decisions,
    loading,
    error,
    refresh: () => setRefreshTick((t) => t + 1),
  };
}
