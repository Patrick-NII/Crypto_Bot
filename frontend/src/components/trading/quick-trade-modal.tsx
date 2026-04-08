"use client";

/**
 * QuickTradeModal — Binance-grade buy/sell modal.
 *
 * Rewritten from scratch to support:
 *   - Market + Limit order types (Stop/OCO/Trailing are V2)
 *   - Base/Quote amount toggle (e.g. 0.5 BTC OR 20 USDT)
 *   - Smart MAX respecting stepSize + MIN_NOTIONAL from exchangeInfo
 *   - 0-100% slider + 25/50/75/MAX presets
 *   - Inline client-side validation (no modal on error)
 *   - Live open orders + recent fills via WebSocket (REST polling fallback)
 *   - Idempotent submission via client_order_id
 *
 * Design notes
 *   - Modal stays a modal (user decision — no side panel) but the inside is
 *     rebuilt to be dense, focused, and never hide essential info.
 *   - The component interface (props) is 100% backward compatible so the
 *     integration at crypto/page.tsx and crypto/[symbol]/client.tsx does NOT
 *     need to change.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Info,
  Loader2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import { tradingApi } from "@/lib/api";
import type { Order, OrderType, SymbolInfo } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useSymbolInfo } from "@/hooks/use-symbol-info";
import { usePreflight } from "@/hooks/use-preflight";
import { useOrdersWs } from "@/hooks/use-orders-ws";
import { useActivePortfolio } from "@/components/providers/portfolio-provider";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const FEE_RATE = 0.001; // fallback only; backend computes the real value

type OrderTypeTab = "market" | "limit" | "stop_limit" | "oco";

const ORDER_TYPE_TO_BACKEND: Record<OrderTypeTab, OrderType> = {
  market: "market",
  limit: "limit",
  stop_limit: "stop_loss",
  oco: "oco",
};
type AmountMode = "base" | "quote";
type Side = "buy" | "sell";

function normalisePair(symbol: string): string {
  if (!symbol) return "";
  return symbol.includes("/") ? symbol.toUpperCase() : `${symbol.toUpperCase()}/USDT`;
}

function splitPair(pair: string): { base: string; quote: string } {
  const [base, quote] = pair.split("/");
  return { base: base || "", quote: quote || "USDT" };
}

function roundDownToStep(value: number, step: number): number {
  if (step <= 0 || !Number.isFinite(value)) return value;
  return Math.floor(value / step) * step;
}

function formatDecimal(value: number, decimals: number): string {
  if (!Number.isFinite(value)) return "0";
  const factor = 10 ** decimals;
  const rounded = Math.round(value * factor) / factor;
  return rounded.toString();
}

function getErrorMessage(raw: unknown): string {
  if (!raw) return "Erreur lors de l'execution. Reessayez.";
  const message = raw instanceof Error ? raw.message : String(raw);
  const lower = message.toLowerCase();

  if (lower.includes("notional") || lower.includes("min_notional") || lower.includes("trop petit"))
    return "Montant trop petit. Augmentez la quantite ou le montant.";
  if (lower.includes("lot_size") || lower.includes("precision") || lower.includes("step"))
    return "Quantite invalide (precision non respectee).";
  if (lower.includes("insufficient") || lower.includes("insuffisant"))
    return "Solde insuffisant pour cet ordre.";
  if (lower.includes("not permitted") || lower.includes("non autoris"))
    return "Cette paire n'est pas autorisee pour votre compte Binance.";
  if (lower.includes("invalid") && lower.includes("key"))
    return "Cle API invalide. Verifiez vos parametres Binance.";
  if (lower.includes("rate") && lower.includes("limit"))
    return "Trop de requetes. Attendez quelques secondes.";
  if (lower.includes("timeout") || lower.includes("synchronis"))
    return "Binance n'a pas repondu a temps. Reessayez.";

  if (message.length < 220 && !message.includes("{")) return message;
  return "Erreur lors de l'execution. Reessayez.";
}

function generateClientOrderId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `ord-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface QuickTradeModalProps {
  symbol: string;
  price: number;
  onClose: () => void;
  onSuccess?: () => void;
  initialSide?: Side;
  initialUsdAmount?: number;
  availableQuote?: number;
  availableBase?: number;
  advisoryText?: string;
  walletAccessEnabled?: boolean;
  walletAccessReason?: string;
  liveTradingEnabled?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

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
  // ------------------------------------------------------------------
  // Core state
  // ------------------------------------------------------------------
  const pair = useMemo(() => normalisePair(symbol), [symbol]);
  const { base: baseAsset, quote: quoteAsset } = useMemo(() => splitPair(pair), [pair]);

  const [side, setSide] = useState<Side>(initialSide);
  const [orderType, setOrderType] = useState<OrderTypeTab>("market");
  const [stopPrice, setStopPrice] = useState<string>("");
  const [stopLimitPrice, setStopLimitPrice] = useState<string>("");
  const [takeProfitPrice, setTakeProfitPrice] = useState<string>("");
  const [amountMode, setAmountMode] = useState<AmountMode>("quote");
  const [amount, setAmount] = useState<string>("");
  const [limitPrice, setLimitPrice] = useState<string>("");
  const [percent, setPercent] = useState<number>(0);
  const [ordersTab, setOrdersTab] = useState<"open" | "history">("open");

  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const clientOrderIdRef = useRef<string | null>(null);

  // ------------------------------------------------------------------
  // Remote data
  // ------------------------------------------------------------------
  const { info: symbolInfo, loading: symbolLoading } = useSymbolInfo(pair);
  const { openOrders, isConnected } = useOrdersWs({
    symbol: pair,
    enabled: true,
  });
  const { active: activePortfolio, portfolios, setActive: setActivePortfolio } = useActivePortfolio();

  // Derived numeric values
  const numericAmount = parseFloat(amount) || 0;
  const numericLimitPrice = parseFloat(limitPrice) || 0;

  const effectivePrice =
    orderType === "limit" && numericLimitPrice > 0 ? numericLimitPrice : Number(price) || 0;

  // Base quantity the user effectively wants to trade
  const baseQuantity = useMemo(() => {
    if (numericAmount <= 0) return 0;
    if (amountMode === "base") return numericAmount;
    if (effectivePrice <= 0) return 0;
    return numericAmount / effectivePrice;
  }, [amountMode, numericAmount, effectivePrice]);

  // Quote quantity the user effectively wants to spend/receive
  const quoteQuantity = useMemo(() => {
    if (numericAmount <= 0) return 0;
    if (amountMode === "quote") return numericAmount;
    return numericAmount * effectivePrice;
  }, [amountMode, numericAmount, effectivePrice]);

  // ------------------------------------------------------------------
  // Preflight (debounced)
  // ------------------------------------------------------------------
  const previewQuantityForPreflight = useMemo(() => {
    if (baseQuantity > 0) return baseQuantity;
    if (effectivePrice > 0) return 5 / effectivePrice;
    return 0;
  }, [baseQuantity, effectivePrice]);

  const { preflight, loading: preflightLoading, error: preflightError, refresh: refreshPreflight } =
    usePreflight({
      symbol: pair,
      side,
      quantity: previewQuantityForPreflight,
      referencePrice: effectivePrice > 0 ? effectivePrice : undefined,
      enabled: pair !== "" && previewQuantityForPreflight > 0,
    });

  const availableQuoteEffective = useMemo(() => {
    if (preflight?.available_quote != null) return Number(preflight.available_quote);
    if (availableQuote != null) return Number(availableQuote);
    return 0;
  }, [preflight, availableQuote]);

  const availableBaseEffective = useMemo(() => {
    if (preflight?.available_base != null) return Number(preflight.available_base);
    if (availableBase != null) return Number(availableBase);
    return 0;
  }, [preflight, availableBase]);

  const minNotional = useMemo(() => {
    if (symbolInfo) return Number(symbolInfo.min_notional);
    if (preflight?.min_notional) return Number(preflight.min_notional);
    return 5;
  }, [symbolInfo, preflight]);

  // ------------------------------------------------------------------
  // Smart MAX (respects stepSize + MIN_NOTIONAL + fee buffer)
  // ------------------------------------------------------------------
  const computeMax = useCallback(
    (mode: AmountMode): number => {
      if (effectivePrice <= 0) return 0;

      const stepSize = symbolInfo ? Number(symbolInfo.step_size) : 0;

      if (side === "sell") {
        // Sell: capped by available base asset
        if (mode === "base") return roundDownToStep(availableBaseEffective, stepSize);
        return roundDownToStep(availableBaseEffective * effectivePrice, 0.01);
      }

      // Buy: capped by quote balance minus a fee buffer
      const feeBuffer = 1 + FEE_RATE * 1.5;
      const maxQuote = availableQuoteEffective / feeBuffer;
      if (mode === "quote") {
        return Math.max(0, maxQuote);
      }
      const rawBase = maxQuote / effectivePrice;
      return roundDownToStep(rawBase, stepSize);
    },
    [side, amountMode, availableQuoteEffective, availableBaseEffective, effectivePrice, symbolInfo],
    // amountMode is stable within the same render; listing it keeps eslint happy
  );

  const maxForCurrentMode = useMemo(() => computeMax(amountMode), [computeMax, amountMode]);

  const applyPercent = useCallback(
    (p: number) => {
      setPercent(p);
      const max = computeMax(amountMode);
      if (max <= 0) return;
      const newAmount = (max * p) / 100;
      if (amountMode === "base" && symbolInfo) {
        setAmount(formatDecimal(newAmount, symbolInfo.base_precision || 6));
      } else {
        setAmount(formatDecimal(newAmount, 2));
      }
    },
    [amountMode, computeMax, symbolInfo],
  );

  // When user manually edits the amount, recompute the slider position.
  useEffect(() => {
    if (maxForCurrentMode <= 0 || numericAmount <= 0) {
      setPercent(0);
      return;
    }
    const ratio = Math.min(100, Math.max(0, (numericAmount / maxForCurrentMode) * 100));
    setPercent(Math.round(ratio));
  }, [numericAmount, maxForCurrentMode]);

  // Reset on symbol change
  useEffect(() => {
    setSide(initialSide);
    setOrderType("market");
    setAmountMode("quote");
    setAmount(initialUsdAmount ? initialUsdAmount.toFixed(2) : "");
    setLimitPrice("");
    setStopPrice("");
    setStopLimitPrice("");
    setTakeProfitPrice("");
    setPercent(0);
    setResult(null);
    clientOrderIdRef.current = null;
  }, [symbol, initialSide, initialUsdAmount]);

  // ------------------------------------------------------------------
  // Client-side validation against exchangeInfo
  // ------------------------------------------------------------------
  const numericStopPrice = parseFloat(stopPrice) || 0;
  const numericStopLimitPrice = parseFloat(stopLimitPrice) || 0;
  const numericTakeProfitPrice = parseFloat(takeProfitPrice) || 0;

  const clientValidation = useMemo((): { ok: boolean; message?: string } => {
    if (numericAmount <= 0) return { ok: false, message: undefined };
    if (orderType === "limit" && numericLimitPrice <= 0) {
      return { ok: false, message: "Entrez un prix limite." };
    }
    if (orderType === "stop_limit") {
      if (numericStopPrice <= 0 || numericStopLimitPrice <= 0) {
        return { ok: false, message: "Stop et Limit prix requis." };
      }
      // Sanity: SL trigger must be the right side of current price
      if (effectivePrice > 0) {
        if (side === "sell" && numericStopPrice >= effectivePrice) {
          return { ok: false, message: "Stop SELL doit etre sous le prix actuel." };
        }
        if (side === "buy" && numericStopPrice <= effectivePrice) {
          return { ok: false, message: "Stop BUY doit etre au-dessus du prix actuel." };
        }
      }
    }
    if (orderType === "oco") {
      if (
        numericTakeProfitPrice <= 0 ||
        numericStopPrice <= 0 ||
        numericStopLimitPrice <= 0
      ) {
        return { ok: false, message: "TP, Stop et Stop Limit requis." };
      }
      if (effectivePrice > 0) {
        if (side === "sell") {
          if (numericTakeProfitPrice <= effectivePrice) {
            return { ok: false, message: "TP SELL doit etre au-dessus du prix actuel." };
          }
          if (numericStopPrice >= effectivePrice) {
            return { ok: false, message: "Stop SELL doit etre sous le prix actuel." };
          }
        }
        if (side === "buy") {
          if (numericTakeProfitPrice >= effectivePrice) {
            return { ok: false, message: "TP BUY doit etre sous le prix actuel." };
          }
          if (numericStopPrice <= effectivePrice) {
            return { ok: false, message: "Stop BUY doit etre au-dessus du prix actuel." };
          }
        }
      }
    }
    if (!symbolInfo) return { ok: true };

    const step = Number(symbolInfo.step_size) || 0;
    const minQty = Number(symbolInfo.min_qty) || 0;
    const maxQty = Number(symbolInfo.max_qty) || Infinity;
    const tick = Number(symbolInfo.tick_size) || 0;

    if (baseQuantity < minQty) {
      return {
        ok: false,
        message: `Quantite minimale : ${minQty} ${symbolInfo.base_asset}`,
      };
    }
    if (baseQuantity > maxQty) {
      return {
        ok: false,
        message: `Quantite maximale : ${maxQty} ${symbolInfo.base_asset}`,
      };
    }
    if (step > 0) {
      const rounded = roundDownToStep(baseQuantity, step);
      if (Math.abs(rounded - baseQuantity) / Math.max(step, 1e-12) > 1e-6) {
        return {
          ok: false,
          message: `La quantite doit etre un multiple de ${step}.`,
        };
      }
    }

    if (quoteQuantity < minNotional) {
      return {
        ok: false,
        message: `Minimum ${minNotional} ${symbolInfo.quote_asset} par ordre.`,
      };
    }

    if (orderType === "limit" && tick > 0) {
      const priceDelta = Math.abs(numericLimitPrice - Math.round(numericLimitPrice / tick) * tick);
      if (priceDelta / Math.max(tick, 1e-12) > 1e-6) {
        return {
          ok: false,
          message: `Le prix doit etre un multiple de ${tick}.`,
        };
      }
    }

    // Balance checks
    if (side === "buy" && quoteQuantity > availableQuoteEffective * (1 + 1e-6)) {
      return {
        ok: false,
        message: `Solde ${symbolInfo.quote_asset} insuffisant.`,
      };
    }
    if (side === "sell" && baseQuantity > availableBaseEffective * (1 + 1e-6)) {
      return {
        ok: false,
        message: `Solde ${symbolInfo.base_asset} insuffisant.`,
      };
    }

    return { ok: true };
  }, [
    numericAmount,
    orderType,
    numericLimitPrice,
    numericStopPrice,
    numericStopLimitPrice,
    numericTakeProfitPrice,
    effectivePrice,
    symbolInfo,
    baseQuantity,
    quoteQuantity,
    minNotional,
    side,
    availableQuoteEffective,
    availableBaseEffective,
  ]);

  // ------------------------------------------------------------------
  // Submission
  // ------------------------------------------------------------------
  const isLimitSell = orderType === "limit" && side === "sell";
  const canUseNativeQuote =
    orderType === "market" && side === "buy" && amountMode === "quote";

  const submitDisabledReason: string | null = useMemo(() => {
    if (submitting) return "Ordre en cours...";
    if (numericAmount <= 0) return "Entrez un montant";
    if (!clientValidation.ok) return clientValidation.message ?? "Entrees invalides";
    if (preflightLoading) return "Verification en cours...";
    if (preflightError && !preflight) return preflightError;
    if (preflight && !preflight.can_execute) return preflight.blocking_reason ?? "Ordre non executable";
    return null;
  }, [submitting, numericAmount, clientValidation, preflightLoading, preflightError, preflight]);

  const submitLabel = useMemo(() => {
    if (submitting) return "";
    const verb = side === "buy" ? "Buy" : "Sell";
    return `${verb} ${baseAsset}`;
  }, [submitting, side, baseAsset]);

  const handleSubmit = useCallback(async () => {
    if (submitDisabledReason) return;
    setSubmitting(true);
    setResult(null);

    // Idempotency — reuse the same id if the user retries within this session
    if (!clientOrderIdRef.current) {
      clientOrderIdRef.current = generateClientOrderId();
    }
    const clientOrderId = clientOrderIdRef.current;

    try {
      const backendType = ORDER_TYPE_TO_BACKEND[orderType];
      const payload: Parameters<typeof tradingApi.placeOrder>[0] = {
        symbol: pair,
        side,
        order_type: backendType,
        client_order_id: clientOrderId,
      };
      if (activePortfolio?.id) {
        payload.portfolio_id = activePortfolio.id;
      }

      if (orderType === "market") {
        if (canUseNativeQuote) {
          payload.quote_quantity = quoteQuantity;
        } else {
          payload.quantity = baseQuantity;
        }
      } else if (orderType === "limit") {
        payload.quantity = baseQuantity;
        payload.price = numericLimitPrice;
      } else if (orderType === "stop_limit") {
        payload.quantity = baseQuantity;
        payload.stop_price = numericStopPrice;
        payload.price = numericStopLimitPrice;
      } else if (orderType === "oco") {
        payload.quantity = baseQuantity;
        // OCO field mapping (cf. backend _execute_live):
        //   price                 = TP limit
        //   stop_price            = SL trigger
        //   take_profit_price     = SL limit (post-trigger)
        payload.price = numericTakeProfitPrice;
        payload.stop_price = numericStopPrice;
        payload.take_profit_price = numericStopLimitPrice;
      }

      const result = await tradingApi.placeOrder(payload);
      let msg: string;
      if (orderType === "limit") {
        msg = `${side === "buy" ? "Achat" : "Vente"} limite placee : ${baseQuantity.toFixed(6)} ${baseAsset} @ ${numericLimitPrice}`;
      } else if (orderType === "stop_limit") {
        msg = `Stop-limit ${side} ${baseQuantity.toFixed(6)} ${baseAsset} @ stop ${numericStopPrice} → limit ${numericStopLimitPrice}`;
      } else if (orderType === "oco") {
        msg = `OCO ${side} ${baseQuantity.toFixed(6)} ${baseAsset} : TP ${numericTakeProfitPrice} / SL ${numericStopPrice}`;
      } else {
        msg = `${side === "buy" ? "Achete" : "Vendu"} ${result.filled_quantity?.toFixed(6) ?? baseQuantity.toFixed(6)} ${baseAsset}`;
      }
      setResult({ ok: true, msg });
      // Reset idempotency after a successful submit; next order is a new intent
      clientOrderIdRef.current = null;
      setAmount("");
      setPercent(0);
      setStopPrice("");
      setStopLimitPrice("");
      setTakeProfitPrice("");
      onSuccess?.();
    } catch (err) {
      setResult({ ok: false, msg: getErrorMessage(err) });
    } finally {
      setSubmitting(false);
    }
  }, [
    submitDisabledReason,
    pair,
    side,
    orderType,
    baseQuantity,
    quoteQuantity,
    numericLimitPrice,
    numericStopPrice,
    numericStopLimitPrice,
    numericTakeProfitPrice,
    canUseNativeQuote,
    baseAsset,
    onSuccess,
    activePortfolio,
  ]);

  const handleCancelOrder = useCallback(async (order: Order) => {
    try {
      await tradingApi.cancelOrder(order.id);
    } catch (err) {
      setResult({ ok: false, msg: getErrorMessage(err) });
    }
  }, []);

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------
  const connectionHint = !walletAccessEnabled
    ? walletAccessReason ?? "Connectez une cle Binance dans Settings pour debloquer l'execution."
    : !liveTradingEnabled
      ? "Le trading n'est pas active sur votre connexion Binance. Activez l'option execution dans Settings."
      : null;

  const quoteToggleDisabled = isLimitSell || (orderType === "market" && side === "sell");
  // Note: MARKET sell could be supported in quote mode with a client-side
  // conversion, but for the V1 we force base entry to keep things simple.

  return (
    <div
      className="fixed inset-0 z-[60] flex items-end justify-center sm:items-center"
      onClick={onClose}
    >
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" />
      <div
        className="relative flex max-h-[92vh] w-full max-w-md flex-col rounded-t-[28px] border border-[var(--glass-border)] sm:rounded-[28px]"
        style={{ background: "var(--surface)", backdropFilter: "blur(28px) saturate(180%)" }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between px-5 pt-5 pb-3 gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-bold text-[var(--foreground)]">{baseAsset}</h2>
              <span className="rounded-md bg-[var(--glass-bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--text-muted)]">
                {quoteAsset}
              </span>
              {isConnected ? (
                <Wifi className="h-3 w-3 text-[var(--success)]" />
              ) : (
                <WifiOff className="h-3 w-3 text-[var(--text-muted)]" />
              )}
            </div>
            <p className="text-sm text-[var(--text-secondary)]">
              {effectivePrice > 0
                ? `${effectivePrice.toLocaleString(undefined, {
                    minimumFractionDigits: 2,
                    maximumFractionDigits: Math.max(2, symbolInfo?.quote_precision ?? 2),
                  })} ${quoteAsset}`
                : "Prix indisponible"}
            </p>
            {portfolios.length > 0 && (
              <div className="mt-1.5 flex items-center gap-1.5 text-[10px] text-[var(--text-muted)]">
                <span>Portfolio :</span>
                <select
                  value={activePortfolio?.id ?? ""}
                  onChange={(e) => {
                    if (e.target.value) void setActivePortfolio(e.target.value);
                  }}
                  className="rounded border border-[var(--glass-border)] bg-[var(--glass-bg)] px-1.5 py-0.5 text-[10px] font-semibold text-[var(--foreground)] outline-none"
                >
                  {portfolios.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                      {p.is_default ? " (default)" : ""}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
          <button
            onClick={onClose}
            className="rounded-xl p-2 text-[var(--text-muted)] hover:bg-[var(--glass-bg)]"
            aria-label="Fermer"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable content */}
        <div className="flex-1 overflow-y-auto px-5 pb-5">
          {/* Buy/Sell tabs */}
          <div
            className="mb-4 flex rounded-xl p-1"
            style={{ background: "var(--glass-bg)" }}
          >
            <button
              onClick={() => setSide("buy")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
                side === "buy"
                  ? "bg-[var(--success)] text-white shadow-lg"
                  : "text-[var(--text-secondary)]",
              )}
            >
              <ArrowUpRight className="h-4 w-4" /> Buy
            </button>
            <button
              onClick={() => setSide("sell")}
              className={cn(
                "flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm font-semibold transition-all",
                side === "sell"
                  ? "bg-[var(--danger)] text-white shadow-lg"
                  : "text-[var(--text-secondary)]",
              )}
            >
              <ArrowDownRight className="h-4 w-4" /> Sell
            </button>
          </div>

          {/* Order type tabs */}
          <div className="mb-4 flex gap-4 border-b border-[var(--glass-border)] text-xs">
            {(["market", "limit", "stop_limit", "oco"] as OrderTypeTab[]).map((type) => (
              <button
                key={type}
                onClick={() => setOrderType(type)}
                className={cn(
                  "pb-2 font-semibold transition-colors",
                  orderType === type
                    ? "border-b-2 border-[var(--page-accent)] text-[var(--foreground)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
                )}
              >
                {type === "market" && "Market"}
                {type === "limit" && "Limit"}
                {type === "stop_limit" && "Stop-Limit"}
                {type === "oco" && "OCO"}
              </button>
            ))}
          </div>

          {advisoryText && (
            <div
              className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]"
              style={{ background: "var(--glass-bg)" }}
            >
              {advisoryText}
            </div>
          )}

          {connectionHint && (
            <div
              className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs leading-5 text-[var(--text-secondary)]"
              style={{ background: "var(--glass-bg)" }}
            >
              <div className="flex items-start gap-2">
                <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--page-accent)]" />
                <div>
                  <p className="font-semibold text-[var(--foreground)]">Connexion Binance requise</p>
                  <p className="mt-1">{connectionHint}</p>
                  <Link
                    href="/settings"
                    className="mt-2 inline-flex items-center gap-1 rounded-lg border border-[var(--glass-border)] px-2.5 py-1.5 text-[11px] font-semibold text-[var(--foreground)] hover:bg-[var(--glass-bg)]"
                  >
                    Ouvrir Settings <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              </div>
            </div>
          )}

          {/* Limit price input */}
          {orderType === "limit" && (
            <div className="mb-3">
              <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                Prix limite ({quoteAsset})
              </label>
              <input
                type="number"
                inputMode="decimal"
                value={limitPrice}
                onChange={(e) => setLimitPrice(e.target.value)}
                placeholder={effectivePrice > 0 ? effectivePrice.toFixed(2) : "0.00"}
                className="w-full rounded-xl border border-[var(--glass-border)] px-4 py-3 text-base font-semibold text-[var(--foreground)] outline-none"
                style={{ background: "var(--glass-bg)" }}
              />
            </div>
          )}

          {/* Stop-Limit fields */}
          {orderType === "stop_limit" && (
            <div className="mb-3 grid grid-cols-2 gap-2">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                  Stop ({quoteAsset})
                </label>
                <input
                  type="number"
                  inputMode="decimal"
                  value={stopPrice}
                  onChange={(e) => setStopPrice(e.target.value)}
                  placeholder="trigger"
                  className="w-full rounded-xl border border-[var(--glass-border)] px-3 py-2.5 text-sm font-semibold text-[var(--foreground)] outline-none"
                  style={{ background: "var(--glass-bg)" }}
                />
              </div>
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                  Limit ({quoteAsset})
                </label>
                <input
                  type="number"
                  inputMode="decimal"
                  value={stopLimitPrice}
                  onChange={(e) => setStopLimitPrice(e.target.value)}
                  placeholder="post-trigger price"
                  className="w-full rounded-xl border border-[var(--glass-border)] px-3 py-2.5 text-sm font-semibold text-[var(--foreground)] outline-none"
                  style={{ background: "var(--glass-bg)" }}
                />
              </div>
            </div>
          )}

          {/* OCO fields */}
          {orderType === "oco" && (
            <div className="mb-3 space-y-2">
              <div>
                <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                  Take-Profit ({quoteAsset})
                </label>
                <input
                  type="number"
                  inputMode="decimal"
                  value={takeProfitPrice}
                  onChange={(e) => setTakeProfitPrice(e.target.value)}
                  placeholder="upper limit"
                  className="w-full rounded-xl border border-[var(--glass-border)] px-3 py-2.5 text-sm font-semibold text-[var(--foreground)] outline-none"
                  style={{ background: "var(--glass-bg)" }}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                    Stop trigger
                  </label>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={stopPrice}
                    onChange={(e) => setStopPrice(e.target.value)}
                    placeholder="trigger"
                    className="w-full rounded-xl border border-[var(--glass-border)] px-3 py-2.5 text-sm font-semibold text-[var(--foreground)] outline-none"
                    style={{ background: "var(--glass-bg)" }}
                  />
                </div>
                <div>
                  <label className="mb-1 block text-[11px] font-medium text-[var(--text-muted)]">
                    Stop limit
                  </label>
                  <input
                    type="number"
                    inputMode="decimal"
                    value={stopLimitPrice}
                    onChange={(e) => setStopLimitPrice(e.target.value)}
                    placeholder="post-trigger"
                    className="w-full rounded-xl border border-[var(--glass-border)] px-3 py-2.5 text-sm font-semibold text-[var(--foreground)] outline-none"
                    style={{ background: "var(--glass-bg)" }}
                  />
                </div>
              </div>
            </div>
          )}

          {/* Amount input with Base/Quote toggle */}
          <div className="mb-3">
            <div className="mb-1 flex items-center justify-between text-[11px]">
              <span className="text-[var(--text-muted)]">
                {side === "buy" ? "Vous depensez" : "Vous vendez"}
              </span>
              <div
                className="flex rounded-md p-0.5 text-[10px] font-semibold"
                style={{ background: "var(--glass-bg)" }}
              >
                <button
                  type="button"
                  disabled={quoteToggleDisabled}
                  onClick={() => setAmountMode("quote")}
                  className={cn(
                    "rounded px-2 py-0.5 transition-all disabled:opacity-40",
                    amountMode === "quote"
                      ? "bg-[var(--page-accent)]/20 text-[var(--page-accent)]"
                      : "text-[var(--text-muted)]",
                  )}
                >
                  {quoteAsset}
                </button>
                <button
                  type="button"
                  onClick={() => setAmountMode("base")}
                  className={cn(
                    "rounded px-2 py-0.5 transition-all",
                    amountMode === "base"
                      ? "bg-[var(--page-accent)]/20 text-[var(--page-accent)]"
                      : "text-[var(--text-muted)]",
                  )}
                >
                  {baseAsset}
                </button>
              </div>
            </div>
            <div
              className={cn(
                "flex items-center rounded-xl border px-5 py-4 transition-colors",
                !clientValidation.ok && numericAmount > 0
                  ? "border-[var(--danger)]/50"
                  : "border-[var(--glass-border)]",
              )}
              style={{ background: "var(--glass-bg)" }}
            >
              <input
                type="number"
                inputMode="decimal"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="0.00"
                className="flex-1 bg-transparent text-2xl font-bold text-[var(--foreground)] outline-none placeholder-[var(--text-muted)]/30"
                autoFocus
              />
              <span className="ml-2 text-sm font-semibold text-[var(--text-muted)]">
                {amountMode === "quote" ? quoteAsset : baseAsset}
              </span>
            </div>

            {/* Conversion hint */}
            {numericAmount > 0 && effectivePrice > 0 && (
              <p className="mt-1.5 text-[11px] text-[var(--text-muted)]">
                {amountMode === "quote"
                  ? `≈ ${formatDecimal(baseQuantity, symbolInfo?.base_precision ?? 6)} ${baseAsset}`
                  : `≈ ${quoteQuantity.toFixed(2)} ${quoteAsset}`}
              </p>
            )}
          </div>

          {/* Percent slider + presets */}
          {maxForCurrentMode > 0 && (
            <div className="mb-4">
              <div className="mb-2 flex items-center justify-between text-[11px] text-[var(--text-muted)]">
                <span>Slider</span>
                <span>
                  Max: {formatDecimal(maxForCurrentMode, amountMode === "base" ? (symbolInfo?.base_precision ?? 6) : 2)} {amountMode === "base" ? baseAsset : quoteAsset}
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={1}
                value={percent}
                onChange={(e) => applyPercent(Number(e.target.value))}
                className="w-full accent-[var(--page-accent)]"
              />
              <div className="mt-2 grid grid-cols-4 gap-2">
                {[25, 50, 75, 100].map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => applyPercent(p)}
                    className={cn(
                      "rounded-lg py-1.5 text-[11px] font-semibold transition-all",
                      percent === p
                        ? "bg-[var(--page-accent)]/15 text-[var(--page-accent)]"
                        : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
                    )}
                    style={{ background: percent === p ? undefined : "var(--glass-bg)" }}
                  >
                    {p === 100 ? "MAX" : `${p}%`}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Order summary */}
          <div
            className="mb-3 rounded-xl border border-[var(--glass-border)] px-4 py-3 text-xs"
            style={{ background: "var(--glass-bg)" }}
          >
            <SummaryRow
              label="Disponible"
              value={
                side === "buy"
                  ? `${availableQuoteEffective.toFixed(2)} ${quoteAsset}`
                  : `${availableBaseEffective.toFixed(symbolInfo?.base_precision ?? 6)} ${baseAsset}`
              }
            />
            <SummaryRow
              label="Minimum d'ordre"
              value={
                symbolLoading
                  ? "..."
                  : `${minNotional.toFixed(2)} ${quoteAsset}`
              }
            />
            <SummaryRow
              label="Frais estimes"
              value={
                numericAmount > 0
                  ? `≈ ${(quoteQuantity * FEE_RATE).toFixed(2)} ${quoteAsset}`
                  : "-"
              }
            />
            <div className="mt-2 flex justify-between border-t border-[var(--glass-border)] pt-2 text-[12px] font-semibold">
              <span className="text-[var(--text-secondary)]">
                {side === "buy" ? "Total a payer" : "Total a recevoir"}
              </span>
              <span className="text-[var(--foreground)]">
                {numericAmount > 0 && effectivePrice > 0
                  ? `${(
                      side === "buy"
                        ? quoteQuantity * (1 + FEE_RATE)
                        : Math.max(quoteQuantity * (1 - FEE_RATE), 0)
                    ).toFixed(2)} ${quoteAsset}`
                  : `0.00 ${quoteAsset}`}
              </span>
            </div>
          </div>

          {/* Validation banner */}
          {!clientValidation.ok && clientValidation.message && numericAmount > 0 && (
            <div className="mb-3 rounded-xl border border-[var(--danger)]/20 bg-[var(--danger)]/10 px-4 py-2 text-xs text-[var(--danger)]">
              {clientValidation.message}
            </div>
          )}

          {preflight && !preflight.can_execute && preflight.blocking_reason && clientValidation.ok && (
            <div className="mb-3 flex items-start justify-between gap-2 rounded-xl border border-[var(--danger)]/20 bg-[var(--danger)]/10 px-4 py-2 text-xs text-[var(--danger)]">
              <span>{preflight.blocking_reason}</span>
              <button
                type="button"
                onClick={refreshPreflight}
                className="shrink-0 rounded-md bg-[var(--danger)]/20 px-2 py-0.5 text-[10px] font-semibold hover:bg-[var(--danger)]/30"
              >
                Reessayer
              </button>
            </div>
          )}

          {result && (
            <div
              className={cn(
                "mb-3 rounded-xl p-3 text-center text-sm",
                result.ok
                  ? "bg-[var(--success)]/12 text-[var(--success)]"
                  : "bg-[var(--danger)]/12 text-[var(--danger)]",
              )}
            >
              {result.msg}
            </div>
          )}

          {/* Submit button */}
          <button
            onClick={handleSubmit}
            disabled={submitDisabledReason !== null}
            title={submitDisabledReason ?? `Executer l'ordre ${side === "buy" ? "d'achat" : "de vente"}`}
            className={cn(
              "w-full rounded-xl py-3.5 text-base font-bold transition-all disabled:cursor-not-allowed disabled:opacity-40",
              side === "buy"
                ? "bg-[var(--success)] text-white hover:brightness-110"
                : "bg-[var(--danger)] text-white hover:brightness-110",
            )}
          >
            {submitting ? (
              <Loader2 className="mx-auto h-5 w-5 animate-spin" />
            ) : (
              submitDisabledReason && numericAmount > 0 ? submitDisabledReason : submitLabel
            )}
          </button>

          {/* Open orders section */}
          <div className="mt-6 border-t border-[var(--glass-border)] pt-4">
            <div className="mb-3 flex items-center gap-4 text-xs">
              <button
                onClick={() => setOrdersTab("open")}
                className={cn(
                  "font-semibold transition-colors",
                  ordersTab === "open"
                    ? "text-[var(--foreground)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
                )}
              >
                Open Orders ({openOrders.length})
              </button>
              <button
                onClick={() => setOrdersTab("history")}
                className={cn(
                  "font-semibold transition-colors",
                  ordersTab === "history"
                    ? "text-[var(--foreground)]"
                    : "text-[var(--text-muted)] hover:text-[var(--text-secondary)]",
                )}
              >
                Recent Fills
              </button>
            </div>
            {ordersTab === "open" ? (
              <OpenOrdersList orders={openOrders} onCancel={handleCancelOrder} symbolInfo={symbolInfo} />
            ) : (
              <RecentFills pair={pair} symbolInfo={symbolInfo} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components (inline)
// ---------------------------------------------------------------------------

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between py-0.5">
      <span className="text-[var(--text-muted)]">{label}</span>
      <span className="text-[var(--text-secondary)]">{value}</span>
    </div>
  );
}

function OpenOrdersList({
  orders,
  onCancel,
  symbolInfo,
}: {
  orders: Order[];
  onCancel: (order: Order) => void;
  symbolInfo: SymbolInfo | null;
}) {
  if (orders.length === 0) {
    return (
      <p className="py-6 text-center text-[11px] text-[var(--text-muted)]">
        Aucun ordre ouvert.
      </p>
    );
  }
  const precision = symbolInfo?.base_precision ?? 6;
  return (
    <div className="space-y-1.5">
      {orders.map((order) => (
        <div
          key={order.id}
          className="flex items-center justify-between rounded-lg border border-[var(--glass-border)] px-3 py-2 text-[11px]"
          style={{ background: "var(--glass-bg)" }}
        >
          <div className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                order.side === "buy"
                  ? "bg-[var(--success)]/15 text-[var(--success)]"
                  : "bg-[var(--danger)]/15 text-[var(--danger)]",
              )}
            >
              {order.side}
            </span>
            <span className="text-[var(--foreground)]">{order.order_type.toUpperCase()}</span>
            <span className="text-[var(--text-muted)]">
              {Number(order.quantity).toFixed(precision)} @{" "}
              {order.price ? Number(order.price).toFixed(2) : "market"}
            </span>
          </div>
          <button
            onClick={() => onCancel(order)}
            className="rounded border border-[var(--glass-border)] px-2 py-0.5 text-[10px] font-semibold text-[var(--text-secondary)] hover:bg-[var(--danger)]/10 hover:text-[var(--danger)]"
          >
            Cancel
          </button>
        </div>
      ))}
    </div>
  );
}

function RecentFills({
  pair,
  symbolInfo,
}: {
  pair: string;
  symbolInfo: SymbolInfo | null;
}) {
  const [fills, setFills] = useState<Order[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    tradingApi
      .getOrders()
      .then((orders) => {
        if (cancelled) return;
        setFills(
          orders
            .filter((o) => o.status === "filled" && o.symbol.toUpperCase() === pair.toUpperCase())
            .slice(0, 10),
        );
      })
      .catch(() => {
        if (!cancelled) setFills([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pair]);

  if (loading) {
    return (
      <p className="py-6 text-center text-[11px] text-[var(--text-muted)]">Chargement...</p>
    );
  }
  if (fills.length === 0) {
    return (
      <p className="py-6 text-center text-[11px] text-[var(--text-muted)]">
        Aucun fill recent.
      </p>
    );
  }
  const precision = symbolInfo?.base_precision ?? 6;
  return (
    <div className="space-y-1.5">
      {fills.map((fill) => (
        <div
          key={fill.id}
          className="flex items-center justify-between rounded-lg border border-[var(--glass-border)] px-3 py-2 text-[11px]"
          style={{ background: "var(--glass-bg)" }}
        >
          <div className="flex flex-1 items-center gap-2">
            <span
              className={cn(
                "rounded px-1.5 py-0.5 text-[9px] font-bold uppercase",
                fill.side === "buy"
                  ? "bg-[var(--success)]/15 text-[var(--success)]"
                  : "bg-[var(--danger)]/15 text-[var(--danger)]",
              )}
            >
              {fill.side}
            </span>
            <span className="text-[var(--text-muted)]">
              {Number(fill.quantity).toFixed(precision)} @{" "}
              {fill.filled_price ? Number(fill.filled_price).toFixed(2) : "-"}
            </span>
          </div>
          <span className="text-[var(--text-muted)]">{new Date(fill.created_at).toLocaleTimeString()}</span>
        </div>
      ))}
    </div>
  );
}
