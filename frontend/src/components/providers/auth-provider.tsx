"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { authApi } from "@/lib/api";
import type { UserProfile } from "@/lib/types";

/* ------------------------------------------------------------------ */
/*  Context shape                                                      */
/* ------------------------------------------------------------------ */

interface AuthContextValue {
  /** Current user profile (null while loading or if not authenticated) */
  user: UserProfile | null;
  /** True while the initial fetch is in progress */
  loading: boolean;
  /** True after initial fetch completes (even if it failed) */
  ready: boolean;
  /** User is logged in with a valid profile */
  authenticated: boolean;
  /** True when user has a token but profile hasn't loaded yet */
  connecting: boolean;
  /** User has accepted the latest CGU */
  termsAccepted: boolean;
  /** User has wallet features unlocked */
  walletEnabled: boolean;
  /** Human-readable reason if wallet is locked */
  walletReason: string;
  /** Number of connected exchanges */
  exchangeCount: number;
  /** Live trading allowed */
  liveTradingEnabled: boolean;
  /** Refresh user profile from backend */
  refreshUser: () => Promise<UserProfile | null>;
  /** Store tokens after login/register and fetch profile */
  loginWithTokens: (accessToken: string, refreshToken: string) => Promise<void>;
  /** Clear auth state (logout) */
  clearAuth: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  loading: true,
  ready: false,
  authenticated: false,
  connecting: false,
  termsAccepted: false,
  walletEnabled: false,
  walletReason: "",
  exchangeCount: 0,
  liveTradingEnabled: false,
  refreshUser: async () => null,
  loginWithTokens: async () => {},
  clearAuth: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

/* ------------------------------------------------------------------ */
/*  Provider                                                           */
/* ------------------------------------------------------------------ */

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [ready, setReady] = useState(false);
  const fetchRef = useRef(false);

  const fetchUser = useCallback(async (): Promise<UserProfile | null> => {
    try {
      const token =
        typeof window !== "undefined"
          ? localStorage.getItem("access_token")
          : null;
      if (!token) {
        setUser(null);
        return null;
      }
      const profile = await authApi.getMe();
      setUser(profile);
      return profile;
    } catch {
      setUser(null);
      return null;
    } finally {
      setLoading(false);
      setReady(true);
    }
  }, []);

  // Initial fetch on mount (once only)
  useEffect(() => {
    if (fetchRef.current) return;
    fetchRef.current = true;
    void fetchUser();
  }, [fetchUser]);

  const loginWithTokens = useCallback(
    async (accessToken: string, refreshToken: string) => {
      if (typeof window !== "undefined") {
        localStorage.setItem("access_token", accessToken);
        localStorage.setItem("refresh_token", refreshToken);
        // Remove demo data if switching to real auth
        localStorage.removeItem("demo_user");
      }
      setLoading(true);
      await fetchUser();
    },
    [fetchUser],
  );

  const clearAuth = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      localStorage.removeItem("demo_user");
    }
    setUser(null);
    setLoading(false);
    setReady(true);
  }, []);

  const hasToken =
    typeof window !== "undefined"
      ? Boolean(localStorage.getItem("access_token"))
      : false;

  const value = useMemo<AuthContextValue>(() => {
    const authenticated = user !== null;
    return {
      user,
      loading,
      ready,
      authenticated,
      connecting: hasToken && loading,
      termsAccepted: Boolean(user?.accepted_terms_at),
      walletEnabled: Boolean(user?.wallet_access_enabled),
      walletReason: user?.wallet_access_reason ?? "",
      exchangeCount: user?.connected_exchanges_count ?? 0,
      liveTradingEnabled: Boolean(user?.live_trading_enabled),
      refreshUser: fetchUser,
      loginWithTokens,
      clearAuth,
    };
  }, [user, loading, ready, hasToken, fetchUser, loginWithTokens, clearAuth]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
