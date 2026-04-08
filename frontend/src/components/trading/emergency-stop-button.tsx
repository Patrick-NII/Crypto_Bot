"use client";

import { useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { aiApi } from "@/lib/api";
import { cn } from "@/lib/utils";

interface EmergencyStopButtonProps {
  onStopped?: () => void;
  className?: string;
  compact?: boolean;
}

/**
 * Big red button that cancels every open order and disables the
 * auto-trader immediately. Requires a two-step confirmation.
 */
export function EmergencyStopButton({
  onStopped,
  className,
  compact = false,
}: EmergencyStopButtonProps) {
  const [confirming, setConfirming] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<string | null>(null);

  const handleConfirm = async () => {
    setLoading(true);
    setResult(null);
    try {
      const response = (await aiApi.emergencyStopAutoTrading()) as Record<string, unknown>;
      const cancelled = Number(response.cancelled ?? 0);
      setResult(`Auto stoppe — ${cancelled} ordre(s) annule(s)`);
      onStopped?.();
      setTimeout(() => setConfirming(false), 2500);
    } catch (err) {
      setResult(err instanceof Error ? err.message : "Echec de l'arret");
    } finally {
      setLoading(false);
    }
  };

  if (!confirming) {
    return (
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className={cn(
          "inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger)]/40 bg-[var(--danger)]/8 font-semibold text-[var(--danger)] transition hover:bg-[var(--danger)]/16",
          compact ? "px-2 py-1 text-[11px]" : "px-3 py-2 text-xs",
          className,
        )}
      >
        <AlertTriangle className="h-3.5 w-3.5" />
        Emergency stop
      </button>
    );
  }

  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border border-[var(--danger)]/50 bg-[var(--danger)]/12 px-3 py-2 text-[11px] text-[var(--danger)]",
        className,
      )}
    >
      <AlertTriangle className="h-4 w-4 shrink-0" />
      {result ? (
        <span className="flex-1 truncate">{result}</span>
      ) : (
        <>
          <span className="flex-1">
            Annuler tous les ordres et desactiver l&apos;auto ?
          </span>
          <button
            type="button"
            disabled={loading}
            onClick={() => setConfirming(false)}
            className="rounded bg-[var(--glass-bg)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] hover:brightness-110"
          >
            Non
          </button>
          <button
            type="button"
            disabled={loading}
            onClick={handleConfirm}
            className="rounded bg-[var(--danger)] px-2 py-0.5 text-[10px] font-bold text-white hover:brightness-110 disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-3 w-3 animate-spin" /> : "Confirmer"}
          </button>
        </>
      )}
    </div>
  );
}
