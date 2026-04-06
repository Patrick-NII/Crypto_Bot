"use client";

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

export type CurrencyCode = "usd" | "eur" | "gbp" | "chf" | "jpy";

interface CurrencyInfo {
  code: CurrencyCode;
  symbol: string;
  locale: string;
  label: string;
}

export const CURRENCIES: Record<CurrencyCode, CurrencyInfo> = {
  usd: { code: "usd", symbol: "$", locale: "en-US", label: "US Dollar (USD)" },
  eur: { code: "eur", symbol: "€", locale: "fr-FR", label: "Euro (EUR)" },
  gbp: { code: "gbp", symbol: "£", locale: "en-GB", label: "British Pound (GBP)" },
  chf: { code: "chf", symbol: "CHF", locale: "de-CH", label: "Swiss Franc (CHF)" },
  jpy: { code: "jpy", symbol: "¥", locale: "ja-JP", label: "Japanese Yen (JPY)" },
};

interface CurrencyContextValue {
  currency: CurrencyCode;
  setCurrency: (code: CurrencyCode) => void;
  symbol: string;
  format: (amount: number, decimals?: number) => string;
}

const CurrencyContext = createContext<CurrencyContextValue>({
  currency: "usd",
  setCurrency: () => {},
  symbol: "$",
  format: (n) => `$${n.toFixed(2)}`,
});

export function useCurrency() {
  return useContext(CurrencyContext);
}

const STORAGE_KEY = "gluetrade-currency";

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrencyState] = useState<CurrencyCode>("usd");

  useEffect(() => {
    const saved = localStorage.getItem(STORAGE_KEY) as CurrencyCode | null;
    if (saved && CURRENCIES[saved]) setCurrencyState(saved);
  }, []);

  const setCurrency = useCallback((code: CurrencyCode) => {
    setCurrencyState(code);
    localStorage.setItem(STORAGE_KEY, code);
  }, []);

  const info = CURRENCIES[currency];

  const format = useCallback(
    (amount: number, decimals?: number) => {
      if (amount == null || isNaN(amount)) return `${info.symbol}0.00`;
      const dec = decimals ?? (Math.abs(amount) >= 1 ? 2 : amount >= 0.001 ? 4 : 8);
      try {
        return new Intl.NumberFormat(info.locale, {
          style: "currency",
          currency: info.code.toUpperCase(),
          minimumFractionDigits: dec,
          maximumFractionDigits: dec,
        }).format(amount);
      } catch {
        return `${info.symbol}${amount.toFixed(dec)}`;
      }
    },
    [info],
  );

  return (
    <CurrencyContext.Provider value={{ currency, setCurrency, symbol: info.symbol, format }}>
      {children}
    </CurrencyContext.Provider>
  );
}
