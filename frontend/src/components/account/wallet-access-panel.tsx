"use client";

import Link from "next/link";
import { ArrowRight, KeyRound, LockKeyhole, ShieldCheck } from "lucide-react";
import { cn } from "@/lib/utils";

interface WalletAccessPanelProps {
  title?: string;
  reason?: string;
  compact?: boolean;
  className?: string;
}

const UNLOCK_STEPS = [
  "Accept the platform terms and keep an active plan.",
  "Create your own exchange API key with read-only access first.",
  "Add the connection in Settings, then enable trading only if you want execution.",
];

export function WalletAccessPanel({
  title = "Private wallet data is locked",
  reason = "Connect your own exchange credentials in Settings to unlock balances, wallet value, orders and execution features.",
  compact = false,
  className,
}: WalletAccessPanelProps) {
  return (
    <section
      className={cn(
        "rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)]",
        compact ? "p-4" : "p-5 md:p-6",
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <div className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl bg-[var(--page-accent)]/12 text-[var(--page-accent)]">
          <LockKeyhole className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-[15px] font-semibold text-[var(--foreground)]">{title}</h2>
            <span className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[11px] font-medium text-[var(--text-muted)]">
              Read-only mode
            </span>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-[var(--text-secondary)]">{reason}</p>
        </div>
      </div>

      {!compact && (
        <div className="mt-4 grid gap-2">
          {UNLOCK_STEPS.map((step, index) => (
            <div
              key={step}
              className="flex items-start gap-2 rounded-xl border border-[var(--glass-border)] bg-[var(--background)]/30 px-3 py-2.5"
            >
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--page-accent)]/12 text-[11px] font-semibold text-[var(--page-accent)]">
                {index + 1}
              </span>
              <p className="text-[13px] leading-relaxed text-[var(--text-secondary)]">{step}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 flex flex-wrap items-center gap-2.5">
        <Link
          href="/settings"
          className="inline-flex items-center gap-2 rounded-xl px-3.5 py-2 text-sm font-medium accent-bg accent-text"
        >
          <KeyRound className="h-4 w-4" />
          Open Settings
          <ArrowRight className="h-4 w-4" />
        </Link>
        <Link
          href="/terms"
          className="inline-flex items-center gap-2 rounded-xl border border-[var(--glass-border)] px-3.5 py-2 text-sm font-medium text-[var(--text-secondary)] hover:bg-[var(--background)]/40"
        >
          <ShieldCheck className="h-4 w-4" />
          Read Terms
        </Link>
      </div>
    </section>
  );
}
