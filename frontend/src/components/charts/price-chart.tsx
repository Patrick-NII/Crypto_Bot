"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time, ColorType, CandlestickSeries, LineSeries } from "lightweight-charts";
import { pricesApi } from "@/lib/api";
import { binanceStream } from "@/lib/binance-stream";
import { cn, toChartTime } from "@/lib/utils";
import type { OHLCVPoint } from "@/lib/types";

const CANDLE_INTERVALS = [
  { label: "1m", value: "1m" },
  { label: "5m", value: "5m" },
  { label: "15m", value: "15m" },
  { label: "1h", value: "1h" },
  { label: "4h", value: "4h" },
  { label: "1d", value: "1d" },
] as const;

const DATA_INTERVALS = [
  ...CANDLE_INTERVALS,
  { label: "1w", value: "1w" },
  { label: "1M", value: "1M" },
] as const;

const RANGE_PRESETS = [
  { label: "1D", seconds: 24 * 60 * 60, minInterval: "1m" },
  { label: "1W", seconds: 7 * 24 * 60 * 60, minInterval: "15m" },
  { label: "1M", seconds: 30 * 24 * 60 * 60, minInterval: "1h" },
  { label: "6M", seconds: 182 * 24 * 60 * 60, minInterval: "1d" },
  { label: "1Y", seconds: 365 * 24 * 60 * 60, minInterval: "1d" },
  { label: "5Y", seconds: 5 * 365 * 24 * 60 * 60, minInterval: "1w" },
  { label: "ALL", seconds: null, minInterval: "1w" },
] as const;

const DEFAULT_CANDLE_INTERVAL = "1h";
const DEFAULT_RANGE = "1D";

interface PriceChartProps {
  symbol: string;
  height?: number;
  type?: "candlestick" | "line";
  className?: string;
  showIntervals?: boolean;
  defaultInterval?: string;
  defaultRange?: string;
  realtime?: boolean;
  showLoader?: boolean;
}

interface CandlePoint {
  time: Time;
  open: number;
  high: number;
  low: number;
  close: number;
}

function intervalToSeconds(interval: string): number {
  const unit = interval.slice(-1);
  const value = Number(interval.slice(0, -1));
  if (!Number.isFinite(value) || value <= 0) return 60;
  if (unit === "m") return value * 60;
  if (unit === "h") return value * 3600;
  if (unit === "d") return value * 86400;
  if (unit === "w") return value * 604800;
  return 60;
}

function normalizeCandleInterval(value?: string | null) {
  if (!value) return DEFAULT_CANDLE_INTERVAL;
  const normalized = value.trim().toLowerCase();
  return CANDLE_INTERVALS.find((preset) => preset.value.toLowerCase() === normalized)?.value ?? DEFAULT_CANDLE_INTERVAL;
}

function normalizeRangePreset(value?: string | null) {
  if (!value) return DEFAULT_RANGE;
  const normalized = value.trim().toUpperCase();
  return RANGE_PRESETS.find((preset) => preset.label === normalized)?.label ?? DEFAULT_RANGE;
}

function getDataInterval(value: string) {
  return DATA_INTERVALS.find((preset) => preset.value === value) ?? DATA_INTERVALS[3];
}

function getRangePreset(value: string) {
  return RANGE_PRESETS.find((preset) => preset.label === value) ?? RANGE_PRESETS[0];
}

function resolveEffectiveInterval(activeInterval: string, activeRange: string) {
  const selected = getDataInterval(activeInterval);
  const range = getRangePreset(activeRange);
  const minimumSeconds = intervalToSeconds(range.minInterval);
  const selectedSeconds = intervalToSeconds(selected.value);
  const targetSeconds = Math.max(selectedSeconds, minimumSeconds);
  return DATA_INTERVALS.find((preset) => intervalToSeconds(preset.value) >= targetSeconds) ?? DATA_INTERVALS[DATA_INTERVALS.length - 1];
}

function resolveRequestLimit(activeRange: string, intervalValue: string) {
  const range = getRangePreset(activeRange);
  if (range.seconds == null) return 1000;
  return Math.max(2, Math.min(1000, Math.ceil(range.seconds / intervalToSeconds(intervalValue)) + 1));
}

export function PriceChart({
  symbol,
  height = 300,
  type = "candlestick",
  className,
  showIntervals = false,
  defaultInterval = DEFAULT_CANDLE_INTERVAL,
  defaultRange = DEFAULT_RANGE,
  realtime = true,
  showLoader = true,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeInterval, setActiveInterval] = useState(() => normalizeCandleInterval(defaultInterval));
  const [activeRange, setActiveRange] = useState(() => normalizeRangePreset(defaultRange));
  const lastCandleRef = useRef<CandlePoint | null>(null);
  const selectedInterval = getDataInterval(activeInterval);
  const effectiveInterval = resolveEffectiveInterval(activeInterval, activeRange);
  const requestLimit = resolveRequestLimit(activeRange, effectiveInterval.value);

  const applyData = useCallback((data: OHLCVPoint[]) => {
    if (!seriesRef.current || !chartRef.current || data.length === 0) return false;

    if (type === "candlestick") {
      const candleData = data.map((d) => ({
        time: toChartTime(d.time) as Time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      }));
      (seriesRef.current as ISeriesApi<"Candlestick">).setData(candleData);
      lastCandleRef.current = candleData[candleData.length - 1] ?? null;
    } else {
      const lineData = data.map((d) => ({
        time: toChartTime(d.time) as Time,
        value: d.close,
      }));
      (seriesRef.current as ISeriesApi<"Line">).setData(lineData);
      lastCandleRef.current = null;
    }

    chartRef.current.timeScale().fitContent();
    return true;
  }, [type]);

  // Create chart
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8888a0",
        fontSize: 13,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      crosshair: {
        vertLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" },
        horzLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.06)" },
      timeScale: { borderColor: "rgba(255,255,255,0.06)", timeVisible: true },
    });

    chartRef.current = chart;

    let series: ISeriesApi<"Candlestick"> | ISeriesApi<"Line">;

    if (type === "candlestick") {
      series = chart.addSeries(CandlestickSeries, {
        upColor: "#06d6a0",
        downColor: "#ef4444",
        borderUpColor: "#06d6a0",
        borderDownColor: "#ef4444",
        wickUpColor: "#06d6a0",
        wickDownColor: "#ef4444",
      });
    } else {
      series = chart.addSeries(LineSeries, {
        color: "#06d6a0",
        lineWidth: 2,
        crosshairMarkerBackgroundColor: "#06d6a0",
        priceLineVisible: false,
        lastValueVisible: true,
      });
    }

    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };

    const observer = new ResizeObserver(handleResize);
    observer.observe(containerRef.current);

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height, type]);

  // Fetch data when symbol or interval changes
  const fetchData = useCallback(async () => {
    if (!seriesRef.current || !chartRef.current) return;

    const cachedData = pricesApi.peekOHLCV(symbol, effectiveInterval.value, requestLimit);
    const hasCachedData = cachedData.length > 0;
    if (hasCachedData) {
      applyData(cachedData);
      setLoading(false);
      setError(null);
    } else {
      lastCandleRef.current = null;
      setLoading(true);
      setError(null);
    }

    try {
      const data = await pricesApi.getOHLCV(symbol, effectiveInterval.value, requestLimit);

      if (!data || data.length === 0) {
        if (!hasCachedData) setError("No data available");
        setLoading(false);
        return;
      }

      applyData(data);
      setLoading(false);
    } catch {
      if (!hasCachedData) setError("Failed to load chart data");
      setLoading(false);
    }
  }, [applyData, effectiveInterval.value, requestLimit, symbol]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchData();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchData]);

  // Binance stream live updates (~1s)
  useEffect(() => {
    if (!seriesRef.current || !realtime) return;

    const unsub = binanceStream.subscribe(symbol, (tick) => {
      if (!seriesRef.current) return;
      const now = Math.floor(Date.now() / 1000);

      if (type === "line") {
        (seriesRef.current as ISeriesApi<"Line">).update({
          time: toChartTime(now) as Time,
          value: tick.price,
        });
        return;
      }

      const series = seriesRef.current as ISeriesApi<"Candlestick">;
      const bucketSize = intervalToSeconds(effectiveInterval.value);
      const rawBucketTime = Math.floor(now / bucketSize) * bucketSize;
      const bucketTime = toChartTime(rawBucketTime) as Time;
      const previous = lastCandleRef.current;

      if (!previous || Number(previous.time) !== Number(bucketTime)) {
        const open = previous?.close ?? tick.price;
        const nextCandle: CandlePoint = {
          time: bucketTime,
          open,
          high: Math.max(open, tick.price),
          low: Math.min(open, tick.price),
          close: tick.price,
        };
        lastCandleRef.current = nextCandle;
        series.update(nextCandle);
        return;
      }

      const nextCandle: CandlePoint = {
        ...previous,
        high: Math.max(previous.high, tick.price),
        low: Math.min(previous.low, tick.price),
        close: tick.price,
      };
      lastCandleRef.current = nextCandle;
      series.update(nextCandle);
    });

    return unsub;
  }, [effectiveInterval.value, realtime, symbol, type]);

  return (
    <div className={cn("relative w-full", className)}>
      {showIntervals && (
        <div className="mb-3 space-y-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex flex-wrap items-center gap-1">
              {CANDLE_INTERVALS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setActiveInterval(preset.value)}
                  className={cn(
                    "rounded-lg px-3 py-1 text-xs font-medium transition-all",
                    activeInterval === preset.value
                      ? "bg-[#06d6a0]/15 text-[#06d6a0]"
                      : "text-[#55556a] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#8888a0]",
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap items-center gap-1">
              {RANGE_PRESETS.map((preset) => (
                <button
                  key={preset.label}
                  type="button"
                  onClick={() => setActiveRange(preset.label)}
                  className={cn(
                    "rounded-lg px-3 py-1 text-xs font-medium transition-all",
                    activeRange === preset.label
                      ? "bg-white/[0.08] text-[var(--foreground)]"
                      : "text-[#55556a] hover:bg-[rgba(255,255,255,0.03)] hover:text-[#8888a0]",
                  )}
                >
                  {preset.label}
                </button>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[#6f7088]">
            <span>Granularite {selectedInterval.label}</span>
            <span>
              Vue {activeRange}
              {effectiveInterval.value !== selectedInterval.value ? ` · donnees ${effectiveInterval.label}` : ""}
            </span>
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && showLoader && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-[#14141b]" style={{ height }}>
          <div className="flex flex-col items-center gap-2">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#06d6a0]/20 border-t-[#06d6a0]" />
            <span className="text-xs text-[#8888a0]">Loading chart...</span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-[#14141b]" style={{ height }}>
          <span className="text-xs text-[#55556a]">{error}</span>
        </div>
      )}

      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
