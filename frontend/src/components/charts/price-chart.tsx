"use client";

import { useEffect, useRef, useState } from "react";
import { createChart, type IChartApi, type ISeriesApi, type Time, ColorType, CandlestickSeries, LineSeries } from "lightweight-charts";
import { pricesApi } from "@/lib/api";
import { priceWs } from "@/lib/websocket";
import { cn } from "@/lib/utils";

interface PriceChartProps {
  symbol: string;
  height?: number;
  type?: "candlestick" | "line";
  className?: string;
}

export function PriceChart({
  symbol,
  height = 300,
  type = "candlestick",
  className,
}: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | ISeriesApi<"Line"> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create chart and fetch data
  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: "#8888a0",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.03)" },
        horzLines: { color: "rgba(255,255,255,0.03)" },
      },
      crosshair: {
        vertLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" },
        horzLine: { color: "rgba(6,214,160,0.3)", width: 1, labelBackgroundColor: "#14141b" },
      },
      rightPriceScale: {
        borderColor: "rgba(255,255,255,0.06)",
      },
      timeScale: {
        borderColor: "rgba(255,255,255,0.06)",
        timeVisible: true,
      },
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
        lastValueVisible: false,
      });
    }

    seriesRef.current = series;

    // Fetch historical data
    setLoading(true);
    setError(null);

    pricesApi
      .getOHLCV(symbol)
      .then((data) => {
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
          (series as ISeriesApi<"Candlestick">).setData(candleData);
        } else {
          const lineData = data.map((d) => ({
            time: d.time as Time,
            value: d.close,
          }));
          (series as ISeriesApi<"Line">).setData(lineData);
        }

        chart.timeScale().fitContent();
        setLoading(false);
      })
      .catch(() => {
        setError("Failed to load chart data");
        setLoading(false);
      });

    // Handle resize
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
  }, [symbol, height, type]);

  // Subscribe to live WebSocket updates
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
      }
    });

    return unsub;
  }, [symbol, type]);

  return (
    <div className={cn("relative w-full", className)}>
      {/* Loading skeleton */}
      {loading && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-[#14141b]"
          style={{ height }}
        >
          <div className="flex flex-col items-center gap-2">
            <div className="h-6 w-6 animate-spin rounded-full border-2 border-[#06d6a0]/20 border-t-[#06d6a0]" />
            <span className="text-xs text-[#8888a0]">Loading chart...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {error && !loading && (
        <div
          className="absolute inset-0 z-10 flex items-center justify-center rounded-lg bg-[#14141b]"
          style={{ height }}
        >
          <span className="text-xs text-[#55556a]">{error}</span>
        </div>
      )}

      {/* Chart container */}
      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
