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

export function usePageAccent(accent: string, glow: string) {
  useEffect(() => {
    document.documentElement.style.setProperty("--page-accent", accent);
    document.documentElement.style.setProperty("--page-glow", glow);
    return () => {
      document.documentElement.style.setProperty("--page-accent", "#06d6a0");
      document.documentElement.style.setProperty("--page-glow", "6,214,160");
    };
  }, [accent, glow]);
}

export const PAGE_ACCENTS = {
  dashboard: { accent: "#06d6a0", glow: "6,214,160" },
  crypto: { accent: "#a855f7", glow: "168,85,247" },
  portfolio: { accent: "#3b82f6", glow: "59,130,246" },
  trading: { accent: "#22c55e", glow: "34,197,94" },
  strategies: { accent: "#f59e0b", glow: "245,158,11" },
  alerts: { accent: "#ef4444", glow: "239,68,68" },
  analytics: { accent: "#ec4899", glow: "236,72,153" },
  news: { accent: "#3b82f6", glow: "59,130,246" },
  settings: { accent: "#8888a0", glow: "136,136,160" },
} as const;

/**
 * SVG filter for liquid glass distortion effect.
 * Uses feTurbulence + feDisplacementMap for subtle refraction.
 */
function LiquidGlassFilter() {
  return (
    <svg width="0" height="0" style={{ position: "absolute" }}>
      <defs>
        <filter id="liquid-distortion" x="-10%" y="-10%" width="120%" height="120%">
          <feTurbulence
            type="fractalNoise"
            baseFrequency="0.008"
            numOctaves="2"
            seed="3"
            result="noise"
          />
          <feDisplacementMap
            in="SourceGraphic"
            in2="noise"
            scale="12"
            xChannelSelector="R"
            yChannelSelector="G"
          />
        </filter>
      </defs>
    </svg>
  );
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState<Theme>("dark");
  const [tradingMode, setTradingModeState] = useState<TradingMode>("manual");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    const savedTheme = localStorage.getItem("okamoey-theme") as Theme | null;
    const savedMode = localStorage.getItem("okamoey-trading-mode") as TradingMode | null;
    if (savedTheme) setTheme(savedTheme);
    if (savedMode) setTradingModeState(savedMode);
    setMounted(true);
  }, []);

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
      {mounted && <LiquidGlassFilter />}
      {children}
      {mounted && <div className="orb-center" />}
    </ThemeContext.Provider>
  );
}
