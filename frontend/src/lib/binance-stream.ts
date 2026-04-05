/**
 * Direct Binance WebSocket stream client for real-time ticker data (~1s updates).
 * Uses the public miniTicker stream — no API key needed.
 *
 * Architecture: one shared WebSocket connection using combined streams.
 * When subscriptions change, the connection is rebuilt with the new stream list.
 */

const BINANCE_WS_BASE = "wss://stream.binance.com:9443/stream";
const MAX_RECONNECT_ATTEMPTS = 15;
const BASE_RECONNECT_DELAY_MS = 1000;

export interface BinanceTick {
  symbol: string;   // e.g. "BTC" (stripped of USDT)
  price: number;
  changePct24h: number;
  volume24h: number;
  high24h: number;
  low24h: number;
  time: number;      // event time ms
}

type TickListener = (tick: BinanceTick) => void;

class BinanceStream {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<TickListener>> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private intentionalClose = false;
  private rebuildTimer: ReturnType<typeof setTimeout> | null = null;

  /**
   * Subscribe to real-time ticks for a symbol (e.g. "BTC", "ETH").
   * Returns an unsubscribe function.
   */
  subscribe(symbol: string, callback: TickListener): () => void {
    if (typeof window === "undefined") return () => {};

    const upper = symbol.toUpperCase();
    const isNew = !this.listeners.has(upper);

    if (isNew) {
      this.listeners.set(upper, new Set());
    }
    this.listeners.get(upper)!.add(callback);

    if (isNew) {
      this.scheduleRebuild();
    }

    return () => {
      const set = this.listeners.get(upper);
      if (!set) return;
      set.delete(callback);
      if (set.size === 0) {
        this.listeners.delete(upper);
        this.scheduleRebuild();
      }
    };
  }

  /** Gracefully close the connection. */
  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.rebuildTimer) {
      clearTimeout(this.rebuildTimer);
      this.rebuildTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.reconnectAttempts = 0;
  }

  // -----------------------------------------------------------------------

  /**
   * Debounce connection rebuilds so rapid subscribe/unsubscribe calls
   * don't thrash the WebSocket connection.
   */
  private scheduleRebuild(): void {
    if (this.rebuildTimer) clearTimeout(this.rebuildTimer);
    this.rebuildTimer = setTimeout(() => {
      this.rebuildTimer = null;
      this.buildConnection();
    }, 100);
  }

  /**
   * Build (or rebuild) the combined stream WebSocket URL from current subscriptions.
   */
  private buildConnection(): void {
    // Close existing connection
    if (this.ws) {
      this.intentionalClose = true;
      this.ws.close();
      this.ws = null;
    }

    if (this.listeners.size === 0) return;

    this.intentionalClose = false;
    this.reconnectAttempts = 0;

    // Build combined stream URL: btcusdt@miniTicker/ethusdt@miniTicker/...
    const streams = [...this.listeners.keys()]
      .map((sym) => `${sym.toLowerCase()}usdt@miniTicker`)
      .join("/");

    const url = `${BINANCE_WS_BASE}?streams=${streams}`;

    try {
      this.ws = new WebSocket(url);
    } catch {
      this.scheduleReconnect();
      return;
    }

    this.ws.onopen = () => {
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const wrapper = JSON.parse(event.data as string) as {
          stream: string;
          data: Record<string, string | number>;
        };
        const d = wrapper.data;
        if (!d || !d.s) return;

        // Binance miniTicker fields:
        // s=symbol, c=close, P=priceChangePct, v=volume, h=high, l=low, E=eventTime
        const rawSymbol = String(d.s); // e.g. "BTCUSDT"
        const symbol = rawSymbol.replace(/USDT$/i, "").toUpperCase();

        const tick: BinanceTick = {
          symbol,
          price: Number(d.c),
          changePct24h: Number(d.P),
          volume24h: Number(d.v) * Number(d.c), // base volume * price = quote volume
          high24h: Number(d.h),
          low24h: Number(d.l),
          time: Number(d.E),
        };

        this.dispatch(symbol, tick);
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      this.ws = null;
      if (!this.intentionalClose) {
        this.scheduleReconnect();
      }
    };

    this.ws.onerror = () => {
      // onclose will fire next
    };
  }

  private dispatch(symbol: string, tick: BinanceTick): void {
    const set = this.listeners.get(symbol);
    if (!set) return;
    for (const cb of set) {
      try {
        cb(tick);
      } catch {
        // Prevent one bad listener from breaking others
      }
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) return;

    const delay = BASE_RECONNECT_DELAY_MS * Math.pow(2, Math.min(this.reconnectAttempts, 6));
    this.reconnectAttempts += 1;

    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.buildConnection();
    }, delay);
  }
}

/** Singleton Binance stream client for real-time sparkline data. */
export const binanceStream = new BinanceStream();
