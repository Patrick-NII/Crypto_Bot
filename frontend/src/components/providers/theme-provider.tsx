"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type Theme = "dark" | "light";
type TradingMode = "manual" | "auto";

interface ThemeContextValue {
  theme: Theme;
  toggleTheme: () => void;
  tradingMode: TradingMode;
  setTradingMode: (mode: TradingMode) => void;
  pageAccent: string;
  pageGlow: string;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: "dark",
  toggleTheme: () => {},
  tradingMode: "manual",
  setTradingMode: () => {},
  pageAccent: "#06d6a0",
  pageGlow: "6,214,160",
});

export function useTheme() {
  return useContext(ThemeContext);
}

/** Call this in each page to set its accent color. */
export function usePageAccent(accent: string, glow: string) {
  const { pageAccent } = useTheme();

  useEffect(() => {
    document.documentElement.style.setProperty("--page-accent", accent);
    document.documentElement.style.setProperty("--page-glow", glow);
    return () => {
      // Reset to default on unmount
      document.documentElement.style.setProperty("--page-accent", "#06d6a0");
      document.documentElement.style.setProperty("--page-glow", "6,214,160");
    };
  }, [accent, glow]);
}

// Page accent presets
export const PAGE_ACCENTS = {
  dashboard: { accent: "#06d6a0", glow: "6,214,160" },
  crypto: { accent: "#a855f7", glow: "168,85,247" },
  portfolio: { accent: "#3b82f6", glow: "59,130,246" },
  trading: { accent: "#22c55e", glow: "34,197,94" },
  strategies: { accent: "#f59e0b", glow: "245,158,11" },
  alerts: { accent: "#ef4444", glow: "239,68,68" },
  analytics: { accent: "#ec4899", glow: "236,72,153" },
} as const;

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [tradingMode, setTradingModeState] = useState<TradingMode>("manual");
  const [mounted, setMounted] = useState(false);

  // Load persisted preferences
  useEffect(() => {
    const savedTheme = localStorage.getItem("okamoey-theme") as Theme | null;
    const savedMode = localStorage.getItem("okamoey-trading-mode") as TradingMode | null;
    if (savedTheme) setTheme(savedTheme);
    if (savedMode) setTradingModeState(savedMode);
    setMounted(true);
  }, []);

  // Apply theme to HTML element
  useEffect(() => {
    if (!mounted) return;
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("okamoey-theme", theme);
  }, [theme, mounted]);

  const toggleTheme = useCallback(() => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  }, []);

  const setTradingMode = useCallback((mode: TradingMode) => {
    setTradingModeState(mode);
    localStorage.setItem("okamoey-trading-mode", mode);
  }, []);

  return (
    <ThemeContext.Provider
      value={{
        theme,
        toggleTheme,
        tradingMode,
        setTradingMode,
        pageAccent: "#06d6a0",
        pageGlow: "6,214,160",
      }}
    >
      {children}
      {/* Third animated orb */}
      {mounted && <div className="orb-center" />}
    </ThemeContext.Provider>
  );
}
