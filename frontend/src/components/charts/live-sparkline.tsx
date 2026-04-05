"use client";

import { useEffect, useRef, useCallback, memo } from "react";
import { binanceStream } from "@/lib/binance-stream";

interface LiveSparklineProps {
  symbol: string;
  /** Current live price (passed from parent to seed initial point) */
  price?: number;
  width?: number;
  height?: number;
  /** Max data points to retain (seconds of history) */
  maxPoints?: number;
  /** Positive = green, negative = red, null = auto from data */
  positive?: boolean | null;
  className?: string;
}

interface TickPoint {
  time: number; // ms timestamp
  price: number;
}

/**
 * Real-time sparkline that updates every ~1 second via direct Binance WebSocket.
 * Uses a raw canvas for maximum rendering performance across many instances.
 */
function LiveSparklineInner({
  symbol,
  price,
  width = 100,
  height = 32,
  maxPoints = 120,
  positive = null,
  className,
}: LiveSparklineProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const pointsRef = useRef<TickPoint[]>([]);
  const lastTickRef = useRef<number>(0);
  const rafRef = useRef<number>(0);

  // Seed the first point from the price prop
  useEffect(() => {
    if (price != null && price > 0 && pointsRef.current.length === 0) {
      pointsRef.current.push({ time: Date.now(), price });
      lastTickRef.current = Math.floor(Date.now() / 1000);
    }
  }, [price]);

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = width * dpr;
    const h = height * dpr;

    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }

    ctx.clearRect(0, 0, w, h);

    const pts = pointsRef.current;
    if (pts.length < 2) return;

    const prices = pts.map((p) => p.price);
    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const range = maxP - minP || 1;
    const padding = 2 * dpr;

    // Determine color
    const first = pts[0].price;
    const last = pts[pts.length - 1].price;
    const isUp = positive === true || (positive === null && last >= first);
    const strokeColor = isUp
      ? "rgba(16, 185, 129, 0.9)"
      : "rgba(239, 68, 68, 0.9)";
    const fillColorTop = isUp
      ? "rgba(16, 185, 129, 0.15)"
      : "rgba(239, 68, 68, 0.12)";
    const fillColorBot = "rgba(0, 0, 0, 0)";

    // Build line path
    ctx.beginPath();
    for (let i = 0; i < pts.length; i++) {
      const x = (i / (pts.length - 1)) * (w - padding * 2) + padding;
      const y = h - padding - ((pts[i].price - minP) / range) * (h - padding * 2);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }

    // Stroke
    ctx.strokeStyle = strokeColor;
    ctx.lineWidth = 1.5 * dpr;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";
    ctx.stroke();

    // Fill gradient below
    const lastX = w - padding;
    ctx.lineTo(lastX, h);
    ctx.lineTo(padding, h);
    ctx.closePath();

    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, fillColorTop);
    grad.addColorStop(1, fillColorBot);
    ctx.fillStyle = grad;
    ctx.fill();
  }, [width, height, positive]);

  // Subscribe to Binance stream — real-time ~1s updates
  useEffect(() => {
    const unsub = binanceStream.subscribe(symbol, (tick) => {
      const nowSec = Math.floor(Date.now() / 1000);
      if (nowSec <= lastTickRef.current) {
        // Same second — update the last point in place
        const pts = pointsRef.current;
        if (pts.length > 0) {
          pts[pts.length - 1] = { time: Date.now(), price: tick.price };
        }
      } else {
        // New second — push a new point
        lastTickRef.current = nowSec;
        pointsRef.current.push({ time: Date.now(), price: tick.price });
        if (pointsRef.current.length > maxPoints) {
          pointsRef.current = pointsRef.current.slice(-maxPoints);
        }
      }

      // Schedule a draw on next animation frame
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(draw);
    });

    return () => {
      unsub();
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [symbol, maxPoints, draw]);

  // Also seed/draw when the price prop changes (for initial render before WS connects)
  useEffect(() => {
    if (price != null && price > 0) {
      const nowSec = Math.floor(Date.now() / 1000);
      if (nowSec > lastTickRef.current) {
        lastTickRef.current = nowSec;
        pointsRef.current.push({ time: Date.now(), price });
        if (pointsRef.current.length > maxPoints) {
          pointsRef.current = pointsRef.current.slice(-maxPoints);
        }
      }
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(draw);
    }
  }, [price, maxPoints, draw]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      className={className}
      style={{ width, height, display: "block" }}
      suppressHydrationWarning
    />
  );
}

export const LiveSparkline = memo(LiveSparklineInner);
