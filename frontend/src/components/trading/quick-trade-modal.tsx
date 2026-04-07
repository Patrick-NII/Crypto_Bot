"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { X, ArrowUpRight, ArrowDownRight, Loader2, ArrowRight, Info } from "lucide-react";
import { tradingApi } from "@/lib/api";
import type { OrderPreflight } from "@/lib/types";
import { cn } from "@/lib/utils";

const FEE_RATE = 0.001;
const PRESETS = [10, 25, 50, 100, 500];

function getTradeErrorMessage(raw: string): string {
  const lower = raw.toLowerCase();

  // Montant trop petit
  if (lower.includes("notional") || lower.includes("trop petit") || lower.includes("too small"))
    return "Montant trop petit. Minimum ~5$ par ordre.";

  if (lower.includes("aucun solde") || lower.includes("non executable") || lower.includes("indisponible"))
    return raw;

  // Solde insuffisant
  if ((lower.includes("insufficient") || lower.includes("insuffisant") || lower.includes("solde")) && raw.length <= 220 && !raw.includes("{"))
    return raw;

  if (lower.includes("insufficient") || lower.includes("insuffisant") || lower.includes("solde"))
    return "Solde insuffisant pour cet ordre.";

  // Paire non autorisee
  if (lower.includes("not permitted") || lower.includes("non autoris"))
    return "Cette paire n'est pas autorisee pour votre compte Binance.";

  // Cle API
  if (lower.includes("api") && (lower.includes("invalid") || lower.includes("invalide") || lower.includes("permission")))
    return "Cle API invalide ou permissions manquantes. Verifiez dans Settings.";

  // Precision
  if (lower.includes("precision") || lower.includes("lot_size") || lower.includes("step"))
    return "Quantite invalide (precision non respectee).";

  // Timeout / sync
  if (lower.includes("timeout") || lower.includes("synchronisation"))
    return "Binance n'a pas repondu a temps. Reessayez.";

  // Rate limit
  if (lower.includes("rate") || lower.includes("trop de requete") || lower.includes("ddos"))
    return "Trop de requetes. Attendez quelques secondes.";

  // Si le message backend est deja clair et court, l'afficher tel quel
  if (raw.length <= 220 && !raw.includes("{"))
    return raw;

  return "Erreur lors de l'execution. Reessayez.";
}

interface QuickTradeModalProps {
  symbol: string;
  price: number;
  onClose: () => void;
  onSuccess?: () => void;
  initialSide?: "buy" | "sell";
  initialUsdAmount?: number;
  availableQuote?: number;
  availableBase?: number;
  advisoryText?: string;
  walletAccessEnabled?: boolean;
  walletAccessReason?: string;
  liveTradingEnabled?: boolean;
}

export function QuickTradeModal({
  symbol,
  price,
  onClose,
  onSuccess,
  initialSide = "buy",
  initialUsdAmount,
  availableQuote,
  availableBase,
  advisoryText,
  walletAccessEnabled = true,
  walletAccessReason,
  liveTradingEnabled = true,
}: QuickTradeModalProps) {
  const [side, setSide] = useState<"buy" | "sell">(initialSide);
  const [amount, setAmount] = useState(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
  const [savedQuoteAmount, setSavedQuoteAmount] = useState(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [preflight, setPreflight] = useState<OrderPreflight | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(false);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [preflightRefreshKey, setPreflightRefreshKey] = useState(0);
  const [tradeSymbol, setTradeSymbol] = useState(symbol);
  const [inputMode, setInputMode] = useState<"quote" | "base">("quote");

  const displayAsset = symbol.includes("/") ? symbol.split("/")[0] : symbol;
  const numericAmount = parseFloat(amount) || 0;
  const conversionMode = tradeSymbol !== symbol && inputMode === "base";
  const effectivePrice = Number(preflight?.estimated_price ?? (tradeSymbol === symbol ? price : 0) ?? 0);
  const requestedQuantity =
    inputMode === "base"
      ? numericAmount
      : effectivePrice > 0
        ? numericAmount / effectivePrice
        : 0;
  const fee = (inputMode === "quote" ? numericAmount : requestedQuantity * effectivePrice) * FEE_RATE;
  const previewQuantity = requestedQuantity > 0 ? requestedQuantity : effectivePrice > 0 ? 5 / effectivePrice : 0.000001;
  const connectionHint = !walletAccessEnabled
    ? (walletAccessReason ?? "Connectez une cle Binance dans Settings pour debloquer l'execution.")
    : !liveTradingEnabled
      ? "Le trading n'est pas active sur votre connexion Binance. Activez l'option execution dans Settings."
      : null;
  const tradeBlockingReason = preflightError ?? (numericAmount > 0 ? preflight?.blocking_reason ?? null : null);
  const resolvedPair = preflight?.resolved_symbol ?? (tradeSymbol.includes("/") ? tradeSymbol : `${tradeSymbol}/USDT`);
  const baseAsset = preflight?.base_asset ?? (tradeSymbol.includes("/") ? tradeSymbol.split("/")[0] : tradeSymbol);
  const quoteAsset = preflight?.quote_asset ?? "USDT";
  const preflightQuote = Number(preflight?.available_quote ?? availableQuote ?? 0);
  const preflightBase = Number(preflight?.available_base ?? availableBase ?? 0);
  const minNotional = Number(preflight?.min_notional ?? 0);
  const preflightFee = Number(preflight?.estimated_fee ?? fee);
  const preflightNotional = Number(preflight?.estimated_notional ?? (inputMode === "quote" ? numericAmount : requestedQuantity * effectivePrice));
  const showConversionCta = Boolean(
    inputMode === "quote" &&
    side === "buy" &&
    tradeBlockingReason &&
    preflight?.conversion_symbol &&
    preflight?.conversion_side &&
    preflight?.conversion_from_asset,
  );
  const conversionTargetAsset =
    preflight?.conversion_side === "sell"
      ? (preflight?.conversion_symbol?.split("/")[1] ?? quoteAsset)
      : (preflight?.conversion_symbol?.split("/")[0] ?? quoteAsset);
  const submitLabel =
    tradeSymbol !== symbol && inputMode === "base"
      ? `Convertir en ${side === "buy" ? baseAsset : quoteAsset}`
      : `${side === "buy" ? "Buy" : "Sell"} ${displayAsset}`;

  useEffect(() => {
    setSide(initialSide);
    setAmount(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
    setSavedQuoteAmount(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
    setResult(null);
    setPreflight(null);
    setPreflightError(null);
    setTradeSymbol(symbol);
    setInputMode("quote");
  }, [initialSide, initialUsdAmount, symbol]);

  useEffect(() => {
    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (!tradeSymbol || !Number.isFinite(previewQuantity) || previewQuantity <= 0) {
        setPreflight(null);
        return;
      }

      setPreflightLoading(true);
      setPreflightError(null);
      void tradingApi.preflightOrder({
        symbol: tradeSymbol,
        side,
        quantity: previewQuantity,
        reference_price: tradeSymbol === symbol && price > 0 ? price : undefined,
      })
        .then((payload) => {
          if (!cancelled) setPreflight(payload);
        })
        .catch(() => {
          if (!cancelled) {
            setPreflight(null);
            setPreflightError("Impossible de verifier l'ordre pour le moment. Reessayez dans quelques secondes.");
          }
        })
        .finally(() => {
          if (!cancelled) setPreflightLoading(false);
        });
    }, 180);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [previewQuantity, price, side, tradeSymbol, preflightRefreshKey]);

  const handlePrepareConversion = () => {
    if (!preflight?.conversion_symbol || !preflight?.conversion_side || !preflight?.conversion_required_quantity) return;
    setSavedQuoteAmount(amount);
    setTradeSymbol(preflight.conversion_symbol);
    setInputMode("base");
    setSide(preflight.conversion_side);
    setAmount(Number(preflight.conversion_required_quantity).toFixed(4));
    setResult(null);
    setPreflight(null);
    setPreflightError(null);
  };

  const handleBackToPrimaryTrade = () => {
    setTradeSymbol(symbol);
    setInputMode("quote");
    setSide(initialSide);
    setAmount(savedQuoteAmount || (initialUsdAmount ? initialUsdAmount.toFixed(2) : ""));
    setResult(null);
    setPreflight(null);
    setPreflightError(null);
  };

  const handleTrade = async () => {
    if (numericAmount <= 0 || requestedQuantity <= 0 || tradeBlockingReason || (preflight && !preflight.can_execute)) return;
    setLoading(true);
    setResult(null);
    try {
      await tradingApi.placeOrder({ symbol: tradeSymbol, side, order_type: "market", quantity: requestedQuantity });
      setResult({
        ok: true,
        msg:
          tradeSymbol !== symbol
            ? `Conversion executee: ${requestedQuantity.toFixed(6)} ${baseAsset} via ${resolvedPair}`
            : `${side === "buy" ? "Bought" : "Sold"} ${requestedQuantity.toFixed(6)} ${baseAsset}`,
      });
      onSuccess?.();
    } catch (err: unknown) {
      const detail = err instanceof Error ? err.message : "Order failed";
      setResult({ ok: false, msg: getTradeErrorMessage(detail) });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center" onClick={onClose}>
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-md rounded-t-[32px] sm:rounded-[32px] p-6 border border-[var(--glass-border)]"
        style={{ background: "var(--surface)", backdropFilter: "blur(28px) saturate(180%)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="mb-5 flex items-center justify-between">
          <div>
            <h2 className="text-lg font-bold text-[var(--foreground)]">
              {tradeSymbol !== symbol ? `Conversion via ${resolvedPair}` : displayAsset}
            </h2>
            <p className="text-sm text-[var(--text-secondary)]">
              {effectivePrice > 0
                ? `${effectivePrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })} ${quoteAsset}`
                : "Prix indisponible"}
            </p>
          </div>
          <button onClick={onClose} className="rounded-xl p-2 text-[var(--text-muted)] hover:bg-[var(--glass-bg)]">
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Buy/Sell toggle */}
        <div className="mb-5 flex rounded-xl p-1" style={{ background: "var(--glass-bg)" }}>
          <button
            onClick={() => setSide("buy")}
            disabled={conversionMode}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
              side === "buy" ? "bg-[var(--success)] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowUpRight className="h-4 w-4" /> Buy
          </button>
          <button
            onClick={() => setSide("sell")}
            disabled={conversionMode}
            className={cn(
              "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
              side === "sell" ? "bg-[var(--danger)] text-white shadow-lg" : "text-[var(--text-secondary)]",
            )}
          >
            <ArrowDownRight className="h-4 w-4" /> Sell
          </button>
        </div>

        {/* Advisory text */}
        {advisoryText && (
          <div className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ background: "var(--glass-bg)" }}>
            {advisoryText}
          </div>
        )}

        {connectionHint && (
          <div className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ background: "var(--glass-bg)" }}>
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--page-accent)]" />
              <div>
                <p className="font-semibold text-[var(--foreground)]">Connexion Binance requise</p>
                <p className="mt-1">{connectionHint}</p>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <Link
                    href="/settings"
                    className="inline-flex items-center gap-1 rounded-lg border border-[var(--glass-border)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--foreground)] hover:bg-[var(--glass-bg)]"
                  >
                    Ouvrir Settings
                    <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                  <span className="text-[11px] text-[var(--text-muted)]">1. Ajouter Binance 2. Activer trading 3. Revenir ici</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {tradeSymbol !== symbol && (
          <div className="mb-3 rounded-xl border border-[var(--page-accent)]/20 px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ background: "color-mix(in srgb, var(--page-accent) 10%, transparent)" }}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold text-[var(--foreground)]">Mode conversion</p>
                <p className="mt-1">
                  Vous preparez {side === "buy" ? baseAsset : quoteAsset} via {resolvedPair} pour financer ensuite l'achat de {displayAsset}.
                </p>
              </div>
              <button
                type="button"
                onClick={handleBackToPrimaryTrade}
                className="shrink-0 rounded-lg border border-[var(--glass-border)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--foreground)] hover:bg-[var(--glass-bg)]"
              >
                Retour
              </button>
            </div>
          </div>
        )}

        <div className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs" style={{ background: "var(--glass-bg)" }}>
          <div className="grid grid-cols-2 gap-x-4 gap-y-2">
            <div>
              <span className="text-[var(--text-muted)]">Paire</span>
              <p className="mt-0.5 text-[13px] font-semibold text-[var(--foreground)]">{resolvedPair}</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Devise debitee</span>
              <p className="mt-0.5 text-[13px] font-semibold text-[var(--foreground)]">{side === "buy" ? quoteAsset : baseAsset}</p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Disponible</span>
              <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">
                {side === "buy" ? `${preflightQuote.toFixed(2)} ${quoteAsset}` : `${preflightBase.toFixed(6)} ${baseAsset}`}
              </p>
            </div>
            <div>
              <span className="text-[var(--text-muted)]">Minimum d'ordre</span>
              <p className="mt-0.5 text-[12px] text-[var(--text-secondary)]">
                {minNotional > 0 ? `${minNotional.toFixed(2)} ${quoteAsset}` : "Chargement..."}
              </p>
            </div>
          </div>
          {preflight?.notes?.length ? (
            <div className="mt-2 border-t border-[var(--glass-border)] pt-2">
              {preflight.notes.slice(0, 2).map((note) => (
                <p key={note} className="text-[11px] leading-5 text-[var(--text-muted)]">
                  - {note}
                </p>
              ))}
            </div>
          ) : null}
        </div>

        {showConversionCta && (
          <div className="mb-4 rounded-xl border border-[var(--page-accent)]/20 px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]" style={{ background: "color-mix(in srgb, var(--page-accent) 8%, transparent)" }}>
            <div className="flex items-start gap-2">
              <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--page-accent)]" />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-[var(--foreground)]">
                  Cette paire s'exécute en {quoteAsset}
                </p>
                <p className="mt-1">
                  Votre solde utile est en {preflight?.conversion_from_asset}. Conversion guidée disponible via{" "}
                  {preflight?.conversion_symbol}.
                </p>
                <p className="mt-1 text-[11px] text-[var(--text-muted)]">
                  Objectif: ~{Number(preflight?.conversion_required_quantity ?? 0).toFixed(4)} {conversionTargetAsset}
                  {preflight?.conversion_estimated_spend
                    ? ` • depense estimee ~${Number(preflight.conversion_estimated_spend).toFixed(2)} ${preflight.conversion_from_asset}`
                    : ""}
                </p>
                <div className="mt-2">
                  <button
                    type="button"
                    onClick={handlePrepareConversion}
                    className="inline-flex items-center gap-1 rounded-lg border border-[var(--glass-border)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--foreground)] hover:bg-[var(--glass-bg)]"
                  >
                    Convertir en {conversionTargetAsset}
                    <ArrowRight className="h-3.5 w-3.5" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Amount input with dynamic max */}
        <div className="mb-4">
          {(() => {
            // Compute max allowed input based on preflight balance
            let maxAllowed: number | undefined;
            if (side === "sell" && inputMode === "base" && preflightBase > 0) {
              maxAllowed = preflightBase;
            } else if (side === "buy" && inputMode === "quote" && preflightQuote > 0) {
              maxAllowed = preflightQuote / (1 + FEE_RATE);
            } else if (side === "buy" && inputMode === "base" && preflightQuote > 0 && effectivePrice > 0) {
              maxAllowed = preflightQuote / effectivePrice / (1 + FEE_RATE);
            }
            const exceeds = maxAllowed != null && numericAmount > maxAllowed;
            return (
              <>
                <div
                  className={cn(
                    "flex items-center rounded-xl px-5 py-4 border",
                    exceeds ? "border-[var(--danger)]/40" : "border-[var(--glass-border)]",
                  )}
                  style={{ background: "var(--glass-bg)" }}
                >
                  <span className="mr-2 text-2xl font-bold text-[var(--text-muted)]">
                    {inputMode === "base" ? baseAsset : quoteAsset}
                  </span>
                  <input
                    type="number"
                    value={amount}
                    max={maxAllowed}
                    onChange={(e) => {
                      setAmount(e.target.value);
                      if (inputMode === "quote") setSavedQuoteAmount(e.target.value);
                    }}
                    placeholder="0.00"
                    className="flex-1 bg-transparent text-3xl font-bold text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]/30"
                    autoFocus
                  />
                  {maxAllowed != null && maxAllowed > 0 && (
                    <button
                      type="button"
                      onClick={() => {
                        const capped = maxAllowed!.toFixed(inputMode === "base" ? 6 : 2);
                        setAmount(capped);
                        if (inputMode === "quote") setSavedQuoteAmount(capped);
                      }}
                      className="ml-2 rounded-md bg-[var(--page-accent)]/12 px-2 py-1 text-[10px] font-semibold text-[var(--page-accent)] hover:bg-[var(--page-accent)]/20"
                    >
                      MAX
                    </button>
                  )}
                </div>
                <div className="mt-1.5 flex items-center justify-between text-xs">
                  {numericAmount > 0 ? (
                    <span className="text-[var(--text-muted)]">
                      {inputMode === "quote"
                        ? `\u2248 ${requestedQuantity.toFixed(6)} ${baseAsset}`
                        : `\u2248 ${(side === "buy" ? preflightNotional + preflightFee : Math.max(preflightNotional - preflightFee, 0)).toFixed(2)} ${quoteAsset}`}
                    </span>
                  ) : (
                    <span />
                  )}
                  {maxAllowed != null && (
                    <span className={cn("text-[10px]", exceeds ? "text-[var(--danger)]" : "text-[var(--text-muted)]")}>
                      Max {maxAllowed.toFixed(inputMode === "base" ? 6 : 2)} {inputMode === "base" ? baseAsset : quoteAsset}
                    </span>
                  )}
                </div>
              </>
            );
          })()}
        </div>

        {/* Presets */}
        {inputMode === "quote" ? (
          <div className="mb-5 flex gap-2">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => {
                  setAmount(String(p));
                  setSavedQuoteAmount(String(p));
                }}
                className={cn(
                  "flex-1 rounded-xl py-2.5 text-xs font-medium transition-all border",
                  amount === String(p)
                    ? "border-[var(--page-accent)]/30 bg-[var(--page-accent)]/12 text-[var(--page-accent)]"
                    : "border-[var(--glass-border)] text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
                )}
                style={amount !== String(p) ? { background: "var(--glass-bg)" } : undefined}
              >
                ${p}
              </button>
            ))}
          </div>
        ) : (
          <div className="mb-5 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-[11px] text-[var(--text-muted)]" style={{ background: "var(--glass-bg)" }}>
            Quantite pre-remplie d'apres le besoin estime pour financer l'ordre initial.
          </div>
        )}

        {/* Fee summary */}
        {numericAmount > 0 && (
          <div className="mb-5 space-y-2 rounded-xl p-4 border border-[var(--glass-border)]" style={{ background: "var(--glass-bg)" }}>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">{inputMode === "base" ? "Quantite cible" : "Montant cible"}</span>
              <span className="text-[var(--text-secondary)]">
                {inputMode === "base" ? `${numericAmount.toFixed(4)} ${baseAsset}` : `${numericAmount.toFixed(2)} ${quoteAsset}`}
              </span>
            </div>
            <div className="flex justify-between text-xs">
              <span className="text-[var(--text-muted)]">Frais estimes</span>
              <span className="text-[var(--text-secondary)]">
                {preflightLoading ? "..." : `${preflightFee.toFixed(2)} ${quoteAsset}`}
              </span>
            </div>
            <div className="flex justify-between border-t border-[var(--glass-border)] pt-2 text-xs font-semibold">
              <span className="text-[var(--text-secondary)]">{side === "buy" ? "Debit reel estime" : "Produit estime"}</span>
              <span className="text-[var(--foreground)]">
                {preflightLoading ? "..." : `${(side === "buy" ? preflightNotional + preflightFee : Math.max(preflightNotional - preflightFee, 0)).toFixed(2)} ${quoteAsset}`}
              </span>
            </div>
          </div>
        )}

        {/* Reroute warning when backend changed the pair */}
        {preflight && preflight.resolved_symbol && preflight.resolved_symbol !== (tradeSymbol.includes("/") ? tradeSymbol : `${tradeSymbol}/USDT`) && (
          <div className="mb-3 rounded-xl border border-[var(--warning)]/30 bg-[var(--warning)]/8 px-3 py-2 text-xs text-[var(--warning)]">
            <Info className="inline h-3 w-3 mr-1" />
            Paire reroute automatiquement: {preflight.resolved_symbol}
          </div>
        )}

        {tradeBlockingReason && (
          <div className="mb-4 rounded-xl border border-[var(--danger)]/20 bg-[var(--danger)]/10 px-4 py-3 text-sm text-[var(--danger)] flex items-start justify-between gap-2">
            <span className="flex-1">{tradeBlockingReason}</span>
            {preflightError && (
              <button
                type="button"
                onClick={() => setPreflightRefreshKey((k) => k + 1)}
                className="shrink-0 rounded-md bg-[var(--danger)]/20 px-2 py-1 text-[11px] font-semibold hover:bg-[var(--danger)]/30"
              >
                Reessayer
              </button>
            )}
          </div>
        )}

        {/* Result */}
        {result && (
          <div className={cn("mb-4 rounded-xl p-3 text-center text-sm", result.ok ? "bg-[var(--success)]/12 text-[var(--success)]" : "bg-[var(--danger)]/12 text-[var(--danger)]")}>
            {result.msg}
          </div>
        )}

        {/* Submit with explanatory tooltip when disabled */}
        {(() => {
          const disabledReason: string | null =
            numericAmount <= 0
              ? "Entrez un montant"
              : loading
                ? "Ordre en cours..."
                : preflightLoading
                  ? "Verification en cours..."
                  : tradeBlockingReason
                    ? String(tradeBlockingReason)
                    : preflight == null && numericAmount > 0
                      ? "En attente de la verification"
                      : null;
          const isDisabled = disabledReason !== null;
          return (
            <button
              onClick={handleTrade}
              disabled={isDisabled}
              title={disabledReason ?? `Executer l'ordre ${side === "buy" ? "d'achat" : "de vente"}`}
              className={cn(
                "w-full rounded-xl py-4 text-base font-bold transition-all disabled:opacity-40 disabled:cursor-not-allowed",
                side === "buy" ? "bg-[var(--success)] text-white hover:brightness-110" : "bg-[var(--danger)] text-white hover:brightness-110",
              )}
            >
              {loading ? <Loader2 className="mx-auto h-5 w-5 animate-spin" /> : submitLabel}
            </button>
          );
        })()}
      </div>
    </div>
  );
}
