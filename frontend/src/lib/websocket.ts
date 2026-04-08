import type { CryptoPrice } from "./types";
import { binanceStream, type BinanceTick } from "./binance-stream";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/ws/prices`
    : "ws://localhost:8003/ws/prices");

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;

type PriceListener = (data: CryptoPrice) => void;
type PriceUpdateMap = Record<string, CryptoPrice | Record<string, unknown>>;

class PriceWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<PriceListener>> = new Map();
  private directUnsubs: Map<string, () => void> = new Map();
  private latestBySymbol: Map<string, CryptoPrice> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;
  private intentionalClose = false;

  /** Open the WebSocket connection. Safe to call multiple times. */
  connect(): void {
    if (typeof window === "undefined") return;
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;

    this.intentionalClose = false;

    try {
      this.ws = new WebSocket(WS_URL);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
      this.startHeartbeat();
      this.syncSubscriptions();
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string) as {
          type: string;
          data: Record<string, unknown>;
        };

        if (message.type === "price_update" && message.data) {
          this.handlePriceUpdate(message.data as PriceUpdateMap);
        }

        if (message.type === "ping") {
          this.ws?.send(JSON.stringify({ type: "pong" }));
        }
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.stopHeartbeat();
      this.ws = null;
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire after onerror, triggering reconnect
    };
  }

  /** Gracefully close the connection. */
  disconnect(): void {
    this.intentionalClose = true;
    this.stopHeartbeat();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    for (const unsub of this.directUnsubs.values()) {
      unsub();
    }
    this.directUnsubs.clear();
    this.reconnectAttempts = 0;
  }

  /**
   * Subscribe to live price updates for a symbol.
   * Returns an unsubscribe function.
   */
  subscribe(symbol: string, callback: PriceListener): () => void {
    const upper = symbol.toUpperCase();

    if (!this.listeners.has(upper)) {
      this.listeners.set(upper, new Set());
      this.attachDirectStream(upper);
      this.sendSubscribe(upper);
    }

    this.listeners.get(upper)!.add(callback);
    const cached = this.latestBySymbol.get(upper);
    if (cached) {
      try {
        callback(cached);
      } catch {
        // Ignore callback bootstrap errors
      }
    }

    // Ensure connection is open
    this.connect();

    return () => {
      const set = this.listeners.get(upper);
      if (!set) return;

      set.delete(callback);

      if (set.size === 0) {
        this.listeners.delete(upper);
        const directUnsub = this.directUnsubs.get(upper);
        if (directUnsub) {
          directUnsub();
          this.directUnsubs.delete(upper);
        }
        this.sendUnsubscribe(upper);
      }
    };
  }

  // -----------------------------------------------------------------------
  // Private helpers
  // -----------------------------------------------------------------------

  private dispatch(symbol: string, data: CryptoPrice): void {
    const upper = symbol.toUpperCase();
    this.latestBySymbol.set(upper, data);
    const set = this.listeners.get(upper);
    if (!set) return;
    for (const cb of set) {
      try {
        cb(data);
      } catch {
        // Prevent one bad listener from breaking others
      }
    }
  }

  private handlePriceUpdate(payload: PriceUpdateMap): void {
    if ("symbol" in payload && typeof payload.symbol === "string") {
      this.mergeAndDispatch(payload as unknown as Partial<CryptoPrice>);
      return;
    }

    for (const [symbol, rawValue] of Object.entries(payload)) {
      if (!rawValue || typeof rawValue !== "object") continue;
      this.mergeAndDispatch({
        ...(rawValue as CryptoPrice),
        symbol: symbol.toUpperCase(),
      });
    }
  }

  private attachDirectStream(symbol: string): void {
    if (this.directUnsubs.has(symbol)) return;
    const unsub = binanceStream.subscribe(symbol, (tick) => {
      this.handleDirectTick(tick);
    });
    this.directUnsubs.set(symbol, unsub);
  }

  private handleDirectTick(tick: BinanceTick): void {
    // Preserve the previous 24h change when Binance didn't emit a valid one
    // (e.g. during the first tick window). We use `undefined` so that
    // `mergeAndDispatch`'s `??` fallback kicks in, instead of overwriting a
    // good value with 0 and causing UI flicker.
    const hasPct = Number.isFinite(tick.changePct24h);
    const pct = hasPct ? tick.changePct24h : undefined;
    const openPrice =
      hasPct && pct !== undefined && pct > -99.999
        ? tick.price / (1 + pct / 100)
        : NaN;
    const change24h =
      Number.isFinite(openPrice) && openPrice > 0 ? tick.price - openPrice : undefined;

    this.mergeAndDispatch({
      symbol: tick.symbol,
      price: tick.price,
      ...(change24h !== undefined ? { change_24h: change24h } : {}),
      ...(pct !== undefined ? { change_pct_24h: pct } : {}),
      volume_24h: tick.volume24h,
    });
  }

  private mergeAndDispatch(patch: Partial<CryptoPrice>): void {
    const upper = String(patch.symbol ?? "").toUpperCase();
    if (!upper) return;

    const previous = this.latestBySymbol.get(upper);

    // Merge a single numeric field, keeping the previous value when the patch
    // contains a missing or non-finite number. This is what prevents UI flicker
    // when a tick arrives without a valid 24h change field.
    const mergeNum = (
      patchVal: unknown,
      prevVal: number | undefined,
      fallback = 0,
    ): number => {
      const parsed = patchVal === undefined || patchVal === null ? NaN : Number(patchVal);
      if (Number.isFinite(parsed)) return parsed;
      if (prevVal !== undefined && Number.isFinite(prevVal)) return prevVal;
      return fallback;
    };

    const next: CryptoPrice = {
      symbol: upper,
      name: String(patch.name ?? previous?.name ?? upper),
      price: mergeNum(patch.price, previous?.price),
      change_24h: mergeNum(patch.change_24h, previous?.change_24h),
      change_pct_24h: mergeNum(patch.change_pct_24h, previous?.change_pct_24h),
      volume_24h: mergeNum(patch.volume_24h, previous?.volume_24h),
      market_cap: mergeNum(patch.market_cap, previous?.market_cap),
      sparkline: patch.sparkline ?? previous?.sparkline,
    };

    if (
      previous &&
      previous.price === next.price &&
      previous.change_24h === next.change_24h &&
      previous.change_pct_24h === next.change_pct_24h &&
      previous.volume_24h === next.volume_24h &&
      previous.market_cap === next.market_cap
    ) {
      return;
    }

    this.dispatch(upper, next);
  }

  private sendSubscribe(symbol: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "subscribe", data: { symbols: [symbol] } }));
    }
  }

  private sendUnsubscribe(symbol: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "unsubscribe", data: { symbols: [symbol] } }));
    }
  }

  private syncSubscriptions(): void {
    if (this.ws?.readyState !== WebSocket.OPEN || this.listeners.size === 0) return;
    this.ws.send(
      JSON.stringify({
        type: "subscribe",
        data: { symbols: [...this.listeners.keys()] },
      }),
    );
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 20_000);
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;

    const delay =
      BASE_RECONNECT_DELAY_MS * Math.pow(2, this.reconnectAttempts);
    this.reconnectAttempts += 1;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }
}

/** Singleton WebSocket client for live price data. */
export const priceWs = new PriceWebSocket();
