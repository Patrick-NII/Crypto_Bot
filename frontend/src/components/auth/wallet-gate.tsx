"use client";

import Link from "next/link";
import { Lock, Key, ShieldCheck, ArrowRight } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  WalletGate                                                         */
/*  Wraps wallet-sensitive sections. When wallet access is locked,     */
/*  shows an overlay prompting the user to connect an exchange.        */
/*  Public data (charts, signals, news) is NEVER gated.               */
/* ------------------------------------------------------------------ */

interface WalletGateProps {
  children: React.ReactNode;
  /** Compact mode shows a slim banner instead of full overlay */
  compact?: boolean;
  /** Optional CSS class for the container */
  className?: string;
}

export function WalletGate({ children, compact = false, className }: WalletGateProps) {
  const { walletEnabled, walletReason, loading, authenticated } = useAuth();

  // While loading or if not authenticated, show children normally
  // (AuthGuard handles redirect to login)
  if (loading || !authenticated) {
    return <>{children}</>;
  }

  // Wallet unlocked -> show real content
  if (walletEnabled) {
    return <>{children}</>;
  }

  // Wallet locked -> show gate
  if (compact) {
    return (
      <div className={cn("relative", className)}>
        {/* Blurred children behind */}
        <div className="pointer-events-none select-none blur-sm opacity-40" aria-hidden>
          {children}
        </div>
        {/* Compact banner */}
        <div className="absolute inset-0 flex items-center justify-center">
          <Link
            href="/settings"
            className="flex items-center gap-2 rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-xl px-4 py-2.5 text-[13px] font-medium text-[var(--text-secondary)] hover:text-[var(--foreground)] transition-all"
          >
            <Lock className="h-3.5 w-3.5 text-[var(--text-muted)]" />
            <span>Connectez un exchange pour voir vos donn&eacute;es</span>
            <ArrowRight className="h-3 w-3" />
          </Link>
        </div>
      </div>
    );
  }

  // Full overlay mode
  return (
    <div className={cn("relative", className)}>
      {/* Blurred children behind */}
      <div className="pointer-events-none select-none blur-[6px] opacity-30" aria-hidden>
        {children}
      </div>
      {/* Overlay */}
      <div className="absolute inset-0 flex items-center justify-center bg-[var(--background)]/60 backdrop-blur-sm rounded-2xl">
        <div className="text-center max-w-sm px-6">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
            <Key className="h-5 w-5 text-[var(--text-muted)]" />
          </div>
          <h3 className="text-[15px] font-semibold text-[var(--foreground)] mb-2">
            Acc&egrave;s wallet verrouill&eacute;
          </h3>
          <p className="text-[13px] text-[var(--text-muted)] leading-relaxed mb-4">
            {walletReason ||
              "Connectez votre exchange et acceptez les conditions pour acc\u00e9der \u00e0 vos donn\u00e9es de portefeuille."}
          </p>
          <div className="flex flex-col gap-2">
            <Link
              href="/settings"
              className="flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-semibold accent-bg accent-text transition-all hover:opacity-90"
            >
              <ShieldCheck className="h-4 w-4" />
              Configurer mon exchange
            </Link>
            <p className="text-[11px] text-[var(--text-muted)]">
              Scanner, signaux et graphiques restent accessibles.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
