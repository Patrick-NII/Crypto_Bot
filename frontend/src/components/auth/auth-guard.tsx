"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2, Mail, ShieldCheck, RefreshCw } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";
import { authApi } from "@/lib/api";

/* ------------------------------------------------------------------ */
/*  AuthGuard                                                          */
/*  Wraps protected pages. Shows connecting state, redirects if        */
/*  unauthenticated, blocks if email not verified.                     */
/* ------------------------------------------------------------------ */

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { ready, authenticated, connecting, loading, isVerified, user, refreshUser } = useAuth();
  const [resending, setResending] = useState(false);
  const [resent, setResent] = useState(false);

  useEffect(() => {
    if (ready && !authenticated) {
      router.replace("/login");
    }
  }, [ready, authenticated, router]);

  const handleResend = useCallback(async () => {
    setResending(true);
    try {
      await authApi.resendVerification();
      setResent(true);
      setTimeout(() => setResent(false), 30000);
    } catch {
      // ignore
    } finally {
      setResending(false);
    }
  }, []);

  const handleRefresh = useCallback(async () => {
    await refreshUser();
  }, [refreshUser]);

  // Phase 1: Loading
  if (!ready || loading) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="relative">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--glass-bg)] border border-[var(--glass-border)]">
              <ShieldCheck className="h-6 w-6 accent-text" />
            </div>
            <Loader2 className="absolute -bottom-1 -right-1 h-5 w-5 animate-spin text-[var(--text-muted)]" />
          </div>
          <div>
            <p className="text-sm font-semibold text-[var(--foreground)]">
              {connecting ? "Connexion en cours..." : "Chargement..."}
            </p>
            <p className="mt-1 text-xs text-[var(--text-muted)]">
              {connecting ? "Verification de votre session" : "Initialisation de la plateforme"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Phase 2: Not authenticated → redirect
  if (!authenticated) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-[var(--text-secondary)]">
          <Loader2 className="h-6 w-6 animate-spin" />
          <p className="text-sm">Redirection vers la page de connexion...</p>
        </div>
      </div>
    );
  }

  // Phase 3: Authenticated but NOT verified → block access
  if (!isVerified) {
    return (
      <div className="flex min-h-[70vh] items-center justify-center px-4">
        <div className="w-full max-w-md rounded-2xl border border-[var(--glass-border)] bg-[var(--glass-bg)] p-8 text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--page-accent)]/12">
            <Mail className="h-8 w-8 text-[var(--page-accent)]" />
          </div>
          <h2 className="text-xl font-bold text-[var(--foreground)] mb-2">
            Verifiez votre email
          </h2>
          <p className="text-sm text-[var(--text-secondary)] mb-1">
            Un email de verification a ete envoye a :
          </p>
          <p className="text-sm font-semibold text-[var(--foreground)] mb-4">
            {user?.email ?? "votre adresse email"}
          </p>
          <p className="text-xs text-[var(--text-muted)] mb-6 leading-relaxed">
            Cliquez sur le lien dans l&apos;email pour activer votre compte.
            Sans verification, votre compte sera desactive automatiquement sous 72h
            conformement a la reglementation europeenne.
          </p>

          <div className="flex flex-col gap-3">
            <button
              onClick={handleResend}
              disabled={resending || resent}
              className="w-full rounded-xl bg-gradient-to-r from-[#06d6a0] to-[#0ff0b3] py-3 text-sm font-semibold text-[#0d0d12] transition-transform hover:scale-[1.01] disabled:opacity-50"
            >
              {resending ? (
                <Loader2 className="mx-auto h-4 w-4 animate-spin" />
              ) : resent ? (
                "Email renvoye ! Verifiez votre boite."
              ) : (
                "Renvoyer l'email de verification"
              )}
            </button>
            <button
              onClick={handleRefresh}
              className="flex items-center justify-center gap-2 rounded-xl border border-[var(--glass-border)] py-2.5 text-sm text-[var(--text-secondary)] hover:bg-[var(--glass-bg)] transition-all"
            >
              <RefreshCw className="h-3.5 w-3.5" />
              J&apos;ai verifie, rafraichir
            </button>
          </div>

          <p className="mt-5 text-[10px] text-[var(--text-muted)]">
            Pensez a verifier vos spams. L&apos;email provient de support@gluetrade.com.
          </p>

          {/* Dev only: skip verification on localhost */}
          {typeof window !== "undefined" && window.location.hostname === "localhost" && (
            <button
              onClick={async () => {
                try {
                  const token = localStorage.getItem("access_token");
                  if (!token) return;
                  await fetch(`${process.env.NEXT_PUBLIC_API_URL ?? "/api/v1"}/auth/dev-verify`, {
                    method: "POST",
                    headers: { Authorization: `Bearer ${token}` },
                  });
                  await refreshUser();
                } catch { /* ignore */ }
              }}
              className="mt-3 w-full rounded-xl border border-dashed border-[#f59e0b]/30 py-2 text-[11px] text-[#f59e0b] hover:bg-[#f59e0b]/5 transition-all"
            >
              [DEV] Passer la verification
            </button>
          )}
        </div>
      </div>
    );
  }

  // Phase 4: Authenticated + verified → render app
  return <>{children}</>;
}
