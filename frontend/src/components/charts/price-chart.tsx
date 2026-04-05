"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time, ColorType, CandlestickSeries, LineSeries } from "lightweight-charts";
import { pricesApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import { cn } from "@/lib/utils";

const INTERVALS = [
  { label: "1H", value: "1m", limit: 60 },
  { label: "4H", value: "5m", limit: 48 },
  { label: "1D", value: "5m", limit: 288 },
  { label: "1W", value: "1h", limit: 168 },
  { label: "1M", value: "4h", limit: 180 },
  { label: "3M", value: "1d", limit: 90 },
  { label: "1Y", value: "1d", limit: 365 },
] as const;

interface PriceChartProps {
  symbol: string;
  height?: number;
  type?: "candlestick" | "line";
  className?: string;
  showIntervals?: boolean;
  defaultInterval?: string;
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

export function PriceChart({
  symbol,
  height = 300,
  type = "candlestick",
  className,
  showIntervals = false,
  defaultInterval = "1M",
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeInterval, setActiveInterval] = useState(defaultInterval);
  const lastCandleRef = useRef<CandlePoint | null>(null);

  const interval = INTERVALS.find((i) => i.label === activeInterval) ?? INTERVALS[3];

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

    setLoading(true);
    setError(null);

    try {
      const data = await pricesApi.getOHLCV(symbol, interval.value, interval.limit);

      if (!data || data.length === 0) {
        setError("No data available");
        setLoading(false);
        return;
      }

      if (type === "candlestick") {
        const candleData = data.map((d) => ({
          time: d.time as Time,
          open: d.open,
          high: d.high,
          low: d.low,
          close: d.close,
        }));
        (seriesRef.current as ISeriesApi<"Candlestick">).setData(candleData);
        lastCandleRef.current = candleData[candleData.length - 1] ?? null;
      } else {
        const lineData = data.map((d) => ({
          time: d.time as Time,
          value: d.close,
        }));
        (seriesRef.current as ISeriesApi<"Line">).setData(lineData);
        lastCandleRef.current = null;
      }

      chartRef.current.timeScale().fitContent();
      setLoading(false);
    } catch {
      setError("Failed to load chart data");
      setLoading(false);
    }
  }, [symbol, interval.value, interval.limit, type]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchData();
    }, 0);
    return () => clearTimeout(timer);
  }, [fetchData]);

  // WebSocket live updates
  useEffect(() => {
    if (!seriesRef.current) return;

    const unsub = priceWs.subscribe(symbol, (priceData) => {
      if (!seriesRef.current) return;
      const now = Math.floor(Date.now() / 1000) as Time;

      if (type === "line") {
        (seriesRef.current as ISeriesApi<"Line">).update({
          time: now,
          value: priceData.price,
        });
        return;
      }

      const series = seriesRef.current as ISeriesApi<"Candlestick">;
      const bucketSize = intervalToSeconds(interval.value);
      const bucketTime = (Math.floor(Number(now) / bucketSize) * bucketSize) as Time;
      const previous = lastCandleRef.current;

      if (!previous || Number(previous.time) !== Number(bucketTime)) {
        const open = previous?.close ?? priceData.price;
        const nextCandle: CandlePoint = {
          time: bucketTime,
          open,
          high: Math.max(open, priceData.price),
          low: Math.min(open, priceData.price),
          close: priceData.price,
        };
        lastCandleRef.current = nextCandle;
        series.update(nextCandle);
        return;
      }

      const nextCandle: CandlePoint = {
        ...previous,
        high: Math.max(previous.high, priceData.price),
        low: Math.min(previous.low, priceData.price),
        close: priceData.price,
      };
      lastCandleRef.current = nextCandle;
      series.update(nextCandle);
    });

    return unsub;
  }, [symbol, type, interval.value]);

  return (
    <div className={cn("relative w-full", className)}>
      {/* Interval selector */}
      {showIntervals && (
        <div className="mb-2 flex gap-1">
          {INTERVALS.map((i) => (
            <button
              key={i.label}
              onClick={() => setActiveInterval(i.label)}
              className={cn(
                "rounded-lg px-3 py-1 text-xs font-medium transition-all",
                activeInterval === i.label
                  ? "bg-[#06d6a0]/15 text-[#06d6a0]"
                  : "text-[#55556a] hover:text-[#8888a0] hover:bg-[rgba(255,255,255,0.03)]",
              )}
            >
              {i.label}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
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
