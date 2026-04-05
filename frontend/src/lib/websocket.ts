import type { CryptoPrice } from "./types";

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

  private handlePriceUpdate(payload: PriceUpdateMap): void {
    if ("symbol" in payload && typeof payload.symbol === "string") {
      const singlePrice = payload as unknown as CryptoPrice;
      this.dispatch(singlePrice.symbol, singlePrice);
      return;
    }

    for (const [symbol, rawValue] of Object.entries(payload)) {
      if (!rawValue || typeof rawValue !== "object") continue;
      const priceData = rawValue as CryptoPrice;
      this.dispatch(priceData.symbol || symbol, {
        ...priceData,
        symbol: (priceData.symbol || symbol).toUpperCase(),
      });
    }
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
