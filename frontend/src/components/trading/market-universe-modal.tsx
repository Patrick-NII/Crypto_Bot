"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, Sparkles, Star, TrendingDown, TrendingUp, X } from "lucide-react";
import { CryptoIcon } from "@/components/ui/crypto-icon";
import { cn } from "@/lib/utils";
import type { MarketUniverseView } from "@/lib/types";

export interface MarketUniverseItem {
  symbol: string;
  name: string;
  price: number;
  changePct24h: number;
  volume24h: number;
  rank: number | null;
  discoveryScore: number;
  image?: string;
}

interface MarketUniverseModalProps {
  open: boolean;
  items: MarketUniverseItem[];
  activeView: MarketUniverseView;
  watchlist: string[];
  onClose: () => void;
  onSelectSymbol: (symbol: string) => void;
  onToggleWatch: (symbol: string) => void;
  onViewChange: (view: MarketUniverseView) => void;
  formatPrice: (value: number, decimals?: number) => string;
}

const VIEW_META: Record<MarketUniverseView, { label: string; icon: typeof Sparkles }> = {
  all: { label: "Toutes", icon: Sparkles },
  gainers: { label: "Gains", icon: TrendingUp },
  losers: { label: "Pertes", icon: TrendingDown },
  candidates: { label: "Candidats", icon: Sparkles },
};

function compactVolume(volume: number) {
  if (volume >= 1_000_000_000) return `${(volume / 1_000_000_000).toFixed(1)}B`;
  if (volume >= 1_000_000) return `${(volume / 1_000_000).toFixed(1)}M`;
  if (volume >= 1_000) return `${(volume / 1_000).toFixed(1)}K`;
  return `${Math.round(volume)}`;
}

export function MarketUniverseModal({
  open,
  items,
  activeView,
  watchlist,
  onClose,
  onSelectSymbol,
  onToggleWatch,
  onViewChange,
  formatPrice,
}: MarketUniverseModalProps) {
  const [query, setQuery] = useState("");

  const handleClose = () => {
    setQuery("");
    onClose();
  };

  const handleSelectSymbol = (symbol: string) => {
    setQuery("");
    onSelectSymbol(symbol);
  };

  useEffect(() => {
    if (!open) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open]);

  const filteredItems = useMemo(() => {
    const trimmed = query.trim().toUpperCase();
    if (!trimmed) return items;
    return items.filter((item) => item.symbol.includes(trimmed) || item.name.toUpperCase().includes(trimmed));
  }, [items, query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center p-4">
      <button
        type="button"
        aria-label="Fermer"
        className="absolute inset-0 bg-black/55 backdrop-blur-sm"
        onClick={handleClose}
      />
      <div className="liquid-glass-strong relative z-[1] flex h-[min(82vh,860px)] w-full max-w-[1120px] flex-col overflow-hidden rounded-[28px] border border-[var(--glass-border)]">
        <div className="flex items-center justify-between gap-4 border-b border-[var(--glass-border)] px-5 py-4">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-[var(--text-muted)]">Market Movers</p>
            <h3 className="text-lg font-semibold text-[var(--foreground)]">Crypto Universe</h3>
          </div>
          <div className="flex min-w-0 flex-1 items-center justify-end gap-3">
            <div className="flex min-w-[220px] max-w-[320px] flex-1 items-center gap-2 rounded-xl border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 py-2">
              <Search className="h-4 w-4 text-[var(--text-muted)]" />
              <input
                type="text"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Rechercher une crypto..."
                className="w-full bg-transparent text-[13px] text-[var(--foreground)] outline-none placeholder:text-[var(--text-muted)]"
              />
            </div>
            <button
              type="button"
              onClick={handleClose}
              className="rounded-xl p-2 text-[var(--text-muted)] transition-colors hover:bg-[var(--glass-bg)] hover:text-[var(--foreground)]"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-2 border-b border-[var(--glass-border)] px-5 py-3">
          {Object.entries(VIEW_META).map(([view, meta]) => {
            const Icon = meta.icon;
            const active = activeView === view;
            return (
              <button
                key={view}
                type="button"
                onClick={() => onViewChange(view as MarketUniverseView)}
                className={cn(
                  "inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-[11px] font-semibold transition-all",
                  active ? "bg-[var(--glass-bg-strong)] text-[var(--foreground)]" : "bg-[var(--glass-bg)] text-[var(--text-muted)] hover:text-[var(--foreground)]",
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {meta.label}
              </button>
            );
          })}
          <span className="ml-auto text-[11px] text-[var(--text-muted)]">{filteredItems.length} actifs</span>
        </div>

        <div className="grid grid-cols-[minmax(0,1.6fr)_120px_92px_96px_64px] gap-3 border-b border-[var(--glass-border)] px-5 py-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-[var(--text-muted)]">
          <span>Actif</span>
          <span className="text-right">Prix</span>
          <span className="text-right">24H</span>
          <span className="text-right">Volume</span>
          <span className="text-right">Watch</span>
        </div>

        <div className="custom-scrollbar flex-1 overflow-y-auto px-2 py-2">
          {filteredItems.map((item) => {
            const isWatched = watchlist.includes(item.symbol);
            return (
              <div
                key={item.symbol}
                role="button"
                tabIndex={0}
                onClick={() => handleSelectSymbol(item.symbol)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" || event.key === " ") handleSelectSymbol(item.symbol);
                }}
                className="grid cursor-pointer grid-cols-[minmax(0,1.6fr)_120px_92px_96px_64px] items-center gap-3 rounded-2xl px-3 py-2 transition-colors hover:bg-[var(--glass-bg)]"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <CryptoIcon symbol={item.symbol} imageUrl={item.image} size="xs" />
                    <span className="truncate text-[13px] font-semibold text-[var(--foreground)]">{item.symbol}</span>
                    {item.rank ? (
                      <span className="rounded-full border border-[var(--glass-border)] px-2 py-0.5 text-[9px] text-[var(--text-muted)]">
                        #{item.rank}
                      </span>
                    ) : null}
                  </div>
                  <p className="truncate text-[11px] text-[var(--text-muted)]">{item.name}</p>
                </div>
                <span className="text-right text-[12px] font-mono text-[var(--foreground)]">{formatPrice(item.price, 2)}</span>
                <span className={cn("text-right text-[12px] font-semibold", item.changePct24h >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]")}>
                  {item.changePct24h >= 0 ? "+" : ""}
                  {item.changePct24h.toFixed(1)}%
                </span>
                <span className="text-right text-[11px] text-[var(--text-secondary)]">{compactVolume(item.volume24h)}</span>
                <div className="flex justify-end">
                  <button
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onToggleWatch(item.symbol);
                    }}
                    className={cn(
                      "rounded-full p-2 transition-colors",
                      isWatched ? "text-[#c6f135]" : "text-[var(--text-muted)] hover:text-[var(--foreground)]",
                    )}
                  >
                    <Star className="h-4 w-4" fill={isWatched ? "currentColor" : "none"} />
                  </button>
                </div>
              </div>
            );
          })}
          {filteredItems.length === 0 ? (
            <div className="flex h-full min-h-[220px] items-center justify-center px-6 text-center text-[12px] text-[var(--text-muted)]">
              Aucun actif ne correspond aux filtres courants.
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
