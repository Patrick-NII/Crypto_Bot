"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, FileText, Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { authApi } from "@/lib/api";
import { cn } from "@/lib/utils";

/* ------------------------------------------------------------------ */
/*  OnboardingModal                                                    */
/*  Shown on first login when user hasn't accepted terms yet.          */
/*  Blocks interaction until CGU are accepted.                         */
/* ------------------------------------------------------------------ */

export function OnboardingModal() {
  const { user, termsAccepted, loading, authenticated, refreshUser } = useAuth();
  const router = useRouter();
  const [accepted, setAccepted] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  // Don't render if loading, not authenticated, or terms already accepted
  if (loading || !authenticated || termsAccepted) {
    return null;
  }

  const handleAccept = async () => {
    if (!accepted) return;
    setSaving(true);
    setError(null);
    try {
      await authApi.acceptTerms("2026-04");
      await refreshUser();
      setDone(true);
      // redirect to settings after a short delay to connect exchange
      setTimeout(() => router.push("/settings"), 1200);
    } catch {
      setError("Impossible d\u2019enregistrer l\u2019acceptation. R\u00e9essayez.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-full max-w-lg mx-4 rounded-2xl border border-[var(--glass-border)] bg-[var(--background)] p-6 shadow-2xl">
        {done ? (
          /* Success state */
          <div className="text-center py-8">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#22c55e]/12">
              <Check className="h-7 w-7 text-[#22c55e]" />
            </div>
            <h2 className="text-xl font-bold text-[var(--foreground)] mb-2">Bienvenue sur GlueTrade</h2>
            <p className="text-[14px] text-[var(--text-muted)]">
              Redirection vers les r&eacute;glages pour connecter votre exchange...
            </p>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="flex items-center gap-3 mb-5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
                <ShieldCheck className="h-5 w-5 accent-text" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-[var(--foreground)]">
                  Conditions d&apos;utilisation
                </h2>
                <p className="text-[13px] text-[var(--text-muted)]">
                  Acceptation requise pour acc&eacute;der &agrave; la plateforme
                </p>
              </div>
            </div>

            {/* CGU Summary */}
            <div className="rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-4 mb-4 max-h-[280px] overflow-y-auto custom-scrollbar space-y-3">
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--foreground)] mb-1">
                  1. Acc&egrave;s et utilisation
                </h3>
                <p className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                  GlueTrade fournit une couche d&apos;intelligence artificielle par-dessus votre compte exchange.
                  Vous restez propri&eacute;taire de vos fonds et de vos cl&eacute;s API &agrave; tout moment.
                </p>
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--foreground)] mb-1">
                  2. Responsabilit&eacute;
                </h3>
                <p className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                  Le trading de cryptomonnaies comporte des risques importants. Les signaux et recommandations
                  de l&apos;IA ne constituent pas des conseils financiers. Vous &ecirc;tes seul responsable
                  de vos d&eacute;cisions d&apos;investissement.
                </p>
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--foreground)] mb-1">
                  3. S&eacute;curit&eacute; des cl&eacute;s API
                </h3>
                <p className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                  Vos cl&eacute;s API sont chiffr&eacute;es (Fernet) et ne sont jamais expos&eacute;es
                  en clair. Nous recommandons de limiter les permissions au strict n&eacute;cessaire
                  et d&apos;activer les restrictions IP sur votre exchange.
                </p>
              </div>
              <div>
                <h3 className="text-[13px] font-semibold text-[var(--foreground)] mb-1">
                  4. Abonnement
                </h3>
                <p className="text-[12px] text-[var(--text-muted)] leading-relaxed">
                  L&apos;acc&egrave;s aux fonctionnalit&eacute;s wallet n&eacute;cessite un abonnement actif
                  (mensuel ou annuel). Les fonctionnalit&eacute;s publiques (scanner, graphiques, signaux)
                  restent accessibles en mode d&eacute;couverte.
                </p>
              </div>
            </div>

            <Link
              href="/terms"
              target="_blank"
              className="flex items-center gap-1.5 text-[12px] text-[var(--page-accent,#8b5cf6)] hover:underline mb-4"
            >
              <FileText className="h-3 w-3" />
              Lire les conditions compl&egrave;tes
            </Link>

            {/* Checkbox */}
            <label className="flex items-start gap-3 cursor-pointer mb-4">
              <input
                type="checkbox"
                checked={accepted}
                onChange={(e) => setAccepted(e.target.checked)}
                className="mt-0.5 h-4 w-4 rounded border-2 border-[var(--glass-border)] accent-[var(--page-accent,#8b5cf6)]"
              />
              <span className="text-[13px] text-[var(--text-secondary)] leading-relaxed">
                J&apos;ai lu et j&apos;accepte les conditions g&eacute;n&eacute;rales d&apos;utilisation
                et la politique de confidentialit&eacute; d&apos;GlueTrade (version 2026-04).
              </span>
            </label>

            {error && (
              <div className="rounded-xl border border-[#ef4444]/20 bg-[#ef4444]/8 px-3 py-2 text-[12px] text-[#ef4444] mb-3">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-[var(--text-muted)]">
                {user?.email}
              </p>
              <button
                onClick={() => void handleAccept()}
                disabled={!accepted || saving}
                className={cn(
                  "flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold transition-all",
                  accepted
                    ? "accent-bg accent-text hover:opacity-90"
                    : "bg-[var(--glass-bg)] text-[var(--text-muted)] cursor-not-allowed",
                )}
              >
                {saving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ShieldCheck className="h-4 w-4" />
                )}
                Accepter et continuer
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
