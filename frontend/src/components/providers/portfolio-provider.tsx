"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { portfolioApi } from "@/lib/api";
import type { Portfolio } from "@/lib/types";
import { useAuth } from "@/components/providers/auth-provider";

const STORAGE_KEY = "gluetrade-active-portfolio";

interface PortfolioContextValue {
  portfolios: Portfolio[];
  active: Portfolio | null;
  loading: boolean;
  refresh: () => Promise<void>;
  setActive: (portfolioId: string) => Promise<void>;
}

const PortfolioContext = createContext<PortfolioContextValue | null>(null);

function readStoredActive(): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistActive(portfolioId: string | null): void {
  if (typeof window === "undefined") return;
  try {
    if (portfolioId) {
      window.localStorage.setItem(STORAGE_KEY, portfolioId);
    } else {
      window.localStorage.removeItem(STORAGE_KEY);
    }
  } catch {
    // ignore
  }
}

export function PortfolioProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [activeId, setActiveId] = useState<string | null>(() => readStoredActive());
  const [loading, setLoading] = useState(false);

  const fetchPortfolios = useCallback(async () => {
    if (!user) {
      setPortfolios([]);
      return;
    }
    setLoading(true);
    try {
      const list = await portfolioApi.list();
      setPortfolios(list);

      // Resolve active portfolio:
      // 1. From localStorage if it still exists in the list
      // 2. Otherwise from the backend default (is_default=true)
      // 3. Otherwise the first portfolio
      const stored = readStoredActive();
      let chosen: Portfolio | null = null;
      if (stored) {
        chosen = list.find((p) => p.id === stored) ?? null;
      }
      if (!chosen) {
        chosen = list.find((p) => p.is_default) ?? list[0] ?? null;
      }
      if (chosen) {
        setActiveId(chosen.id);
        persistActive(chosen.id);
      } else {
        setActiveId(null);
        persistActive(null);
      }
    } catch {
      setPortfolios([]);
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    void fetchPortfolios();
  }, [fetchPortfolios]);

  const setActive = useCallback(
    async (portfolioId: string) => {
      const target = portfolios.find((p) => p.id === portfolioId);
      if (!target) return;
      setActiveId(portfolioId);
      persistActive(portfolioId);
      try {
        await portfolioApi.activate(portfolioId);
        // Refresh to pick up is_default flag changes
        await fetchPortfolios();
      } catch {
        // Soft-fail: keep the local choice even if the backend call failed
      }
    },
    [portfolios, fetchPortfolios],
  );

  const active = useMemo(
    () => portfolios.find((p) => p.id === activeId) ?? null,
    [portfolios, activeId],
  );

  const value = useMemo<PortfolioContextValue>(
    () => ({
      portfolios,
      active,
      loading,
      refresh: fetchPortfolios,
      setActive,
    }),
    [portfolios, active, loading, fetchPortfolios, setActive],
  );

  return <PortfolioContext.Provider value={value}>{children}</PortfolioContext.Provider>;
}

export function useActivePortfolio(): PortfolioContextValue {
  const ctx = useContext(PortfolioContext);
  if (ctx === null) {
    // Soft-fail when used outside the provider — modal still works without the context
    return {
      portfolios: [],
      active: null,
      loading: false,
      refresh: async () => {},
      setActive: async () => {},
    };
  }
  return ctx;
}
