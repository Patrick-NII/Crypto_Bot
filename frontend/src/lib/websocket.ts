import type { CryptoPrice } from "./types";

const WS_URL =
  process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8003/ws/prices";

const MAX_RECONNECT_ATTEMPTS = 10;
const BASE_RECONNECT_DELAY_MS = 1000;

type PriceListener = (data: CryptoPrice) => void;

class PriceWebSocket {
  private ws: WebSocket | null = null;
  private listeners: Map<string, Set<PriceListener>> = new Map();
  private reconnectAttempts = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
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

      // Re-subscribe to all active symbols
      for (const symbol of this.listeners.keys()) {
        this.sendSubscribe(symbol);
      }
    };

    this.ws.onmessage = (event: MessageEvent) => {
      try {
        const message = JSON.parse(event.data as string) as {
          type: string;
          data: Record<string, unknown>;
        };

        if (message.type === "price_update" && message.data) {
          const priceData = message.data as unknown as CryptoPrice;
          const symbol = priceData.symbol;
          if (symbol) {
            this.dispatch(symbol, priceData);
          }
        }

        if (message.type === "ping") {
          this.ws?.send(JSON.stringify({ type: "pong" }));
        }
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
      // onclose will fire after onerror, triggering reconnect
    };
  }

  /** Gracefully close the connection. */
  disconnect(): void {
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
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
      this.sendSubscribe(upper);
    }

    this.listeners.get(upper)!.add(callback);

    // Ensure connection is open
    this.connect();

    return () => {
      const set = this.listeners.get(upper);
      if (!set) return;

      set.delete(callback);

      if (set.size === 0) {
        this.listeners.delete(upper);
        this.sendUnsubscribe(upper);
      }
    };
  }

  // -----------------------------------------------------------------------
  // Private helpers
  // -----------------------------------------------------------------------

  private dispatch(symbol: string, data: CryptoPrice): void {
    const upper = symbol.toUpperCase();
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

  private sendSubscribe(symbol: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "subscribe", symbol }));
    }
  }

  private sendUnsubscribe(symbol: string): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ type: "unsubscribe", symbol }));
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
