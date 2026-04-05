"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2, ShieldCheck } from "lucide-react";
import { useAuth } from "@/components/providers/auth-provider";

/* ------------------------------------------------------------------ */
/*  AuthGuard                                                          */
/*  Wraps protected pages. Shows connecting state, redirects if        */
/*  unauthenticated, and only renders children when ready.             */
/* ------------------------------------------------------------------ */

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { ready, authenticated, connecting, loading } = useAuth();

  useEffect(() => {
    // Once the provider is done loading and user is NOT authenticated -> login
    if (ready && !authenticated) {
      router.replace("/login");
    }
  }, [ready, authenticated, router]);

  // Phase 1: Provider hasn't finished initial fetch yet
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
              {connecting
                ? "V\u00e9rification de votre session"
                : "Initialisation de la plateforme"}
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Phase 2: Provider is done but user is not authenticated -> redirect happening
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

  // Phase 3: Authenticated -> render children
  return <>{children}</>;
}
