"use client";

import type {
  CryptoMarketData,
  PortfolioBalanceSnapshot,
  PortfolioHoldingSnapshot,
  PortfolioSnapshot,
  RiskMetrics,
} from "./types";

export const WALLET_STABLES = new Set([
  "USDT",
  "USDC",
  "BUSD",
  "FDUSD",
  "DAI",
  "TUSD",
  "USD",
  "EUR",
  "USD1",
]);

export interface WalletHoldingView {
  symbol: string;
  available: number;
  reserved: number;
  total: number;
  price: number;
  value: number;
  changePct: number;
  stable: boolean;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
}

function toNumber(value: number | string | null | undefined) {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number.parseFloat(value);
  return 0;
}

function resolveHoldingPrice(
  holding: PortfolioHoldingSnapshot,
  marketBySymbol?: Map<string, CryptoMarketData>,
  livePrices?: Record<string, number>,
) {
  const symbol = holding.symbol.toUpperCase();
  if (holding.stable || WALLET_STABLES.has(symbol)) return 1;

  const livePrice = livePrices?.[symbol];
  if (Number.isFinite(livePrice) && livePrice && livePrice > 0) return livePrice;

  const market = marketBySymbol?.get(symbol);
  const marketPrice = toNumber(market?.current_price ?? market?.price);
  if (marketPrice > 0) return marketPrice;

  return toNumber(holding.price);
}

function snapshotBalanceEntries(snapshot: PortfolioSnapshot): Array<{
  currency: string;
  available: number;
  reserved: number;
  total: number;
}> {
  if (snapshot.balances.length > 0) {
    return snapshot.balances.map((balance: PortfolioBalanceSnapshot) => ({
      currency: balance.currency.toUpperCase(),
      available: toNumber(balance.available),
      reserved: toNumber(balance.reserved),
      total: toNumber(balance.total),
    }));
  }

  return snapshot.holdings.map((holding) => ({
    currency: holding.symbol.toUpperCase(),
    available: toNumber(holding.available),
    reserved: toNumber(holding.reserved),
    total: toNumber(holding.total),
  }));
}

export function listWalletSymbols(snapshot: PortfolioSnapshot): string[] {
  return Array.from(
    new Set(snapshotBalanceEntries(snapshot).map((balance) => balance.currency.toUpperCase())),
  );
}

export function buildWalletHoldings(
  snapshot: PortfolioSnapshot,
  marketBySymbol?: Map<string, CryptoMarketData>,
  livePrices?: Record<string, number>,
): WalletHoldingView[] {
  const holdingsBySymbol = new Map(
    snapshot.holdings.map((holding) => [holding.symbol.toUpperCase(), holding]),
  );

  return snapshotBalanceEntries(snapshot)
    .map((balance) => {
      const symbol = balance.currency.toUpperCase();
      const snapshotHolding =
        holdingsBySymbol.get(symbol) ??
        ({
          symbol,
          available: balance.available,
          reserved: balance.reserved,
          total: balance.total,
          price: 0,
          value: 0,
          change_pct_24h: 0,
          stable: WALLET_STABLES.has(symbol),
        } satisfies PortfolioHoldingSnapshot);
      const stable = snapshotHolding.stable || WALLET_STABLES.has(symbol);
      const price = resolveHoldingPrice(snapshotHolding, marketBySymbol, livePrices);
      const total = toNumber(balance.total);
      const value = stable ? total : total * price;
      const market = marketBySymbol?.get(symbol);
      const changePct = stable
        ? 0
        : toNumber(
            market?.price_change_percentage_24h ??
              market?.change_pct_24h ??
              snapshotHolding.change_pct_24h,
          );

      return {
        symbol,
        available: toNumber(balance.available),
        reserved: toNumber(balance.reserved),
        total,
        price,
        value,
        changePct,
        stable,
      };
    })
    .filter((holding) => holding.total > 0)
    .sort((left, right) => right.value - left.value);
}

export function computeWalletValue(
  holdings: WalletHoldingView[],
  fallback = 0,
) {
  const total = holdings.reduce((sum, holding) => sum + holding.value, 0);
  return total > 0 ? total : fallback;
}

export function computeWalletCashValue(
  holdings: WalletHoldingView[],
  fallback = 0,
) {
  const total = holdings
    .filter((holding) => holding.stable)
    .reduce((sum, holding) => sum + holding.value, 0);
  return total > 0 ? total : fallback;
}

export function computeWalletMarketExposure(
  totalValue: number,
  cashValue: number,
  fallback = 0,
) {
  const exposure = Math.max(totalValue - cashValue, 0);
  return exposure > 0 ? exposure : fallback;
}

export function computeWalletDayChange(
  holdings: WalletHoldingView[],
  totalValue: number,
  fallbackValue = 0,
  fallbackPct = 0,
) {
  const dayChangeValue = holdings
    .filter((holding) => !holding.stable && holding.changePct !== 0 && holding.value > 0)
    .reduce((sum, holding) => {
      return sum + (holding.value - holding.value / (1 + holding.changePct / 100));
    }, 0);

  if (Math.abs(dayChangeValue) < 1e-9) {
    return {
      value: fallbackValue,
      pct: fallbackPct,
    };
  }

  const base = totalValue - dayChangeValue;
  const pct = base > 0 ? (dayChangeValue / base) * 100 : 0;
  return {
    value: dayChangeValue,
    pct,
  };
}

export function hasUsableRiskMetrics(
  riskMetrics: RiskMetrics | null | undefined,
  totalValue: number,
) {
  if (!riskMetrics || riskMetrics.risk_score == null) return false;
  if (totalValue <= 0) return true;

  return (
    riskMetrics.total_value > 0 ||
    riskMetrics.position_risk.length > 0 ||
    riskMetrics.warnings.length > 0
  );
}

export function estimateWalletRiskScore(
  holdings: WalletHoldingView[],
  totalValue: number,
  riskMetrics?: RiskMetrics | null,
) {
  if (riskMetrics && hasUsableRiskMetrics(riskMetrics, totalValue)) {
    return Math.round(clamp(riskMetrics.risk_score, 0, 100));
  }

  if (holdings.length === 0 || totalValue <= 0) return 0;

  const weights = holdings.map((holding) => holding.value / totalValue);
  const hhi = weights.reduce((sum, weight) => sum + weight * weight, 0);
  const weightedVol = holdings.reduce(
    (sum, holding, index) => sum + weights[index] * Math.abs(holding.changePct),
    0,
  );
  const stableRatio =
    holdings
      .filter((holding) => holding.stable)
      .reduce((sum, holding) => sum + holding.value, 0) / totalValue;
  const diversificationPenalty = Math.max(0, 1 - holdings.length / 15);
  const raw =
    hhi * 35 +
    Math.min(weightedVol / 10, 1) * 30 +
    diversificationPenalty * 15 +
    (1 - stableRatio) * 20;

  return Math.round(clamp(raw, 0, 100));
}

export function formatWalletRiskLevel(level?: RiskMetrics["risk_level"]) {
  return level ? `${level.charAt(0).toUpperCase()}${level.slice(1)}` : null;
}
