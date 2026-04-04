/**
 * Binance API Proxy — runs locally to keep API keys server-side.
 * Reads keys from ../.env, proxies requests to Binance with HMAC signature.
 *
 * Usage: node binance-proxy.mjs
 * Runs on port 3001
 */

import { createServer } from "node:http";
import { createHmac } from "node:crypto";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));

// Load .env from parent directory
let API_KEY = "";
let SECRET_KEY = "";
try {
  const envContent = readFileSync(join(__dirname, "..", ".env"), "utf-8");
  for (const line of envContent.split("\n")) {
    const [key, ...rest] = line.split("=");
    const val = rest.join("=").trim().replace(/^["']|["']$/g, "");
    if (key.trim() === "BINANCE_API_KEY") API_KEY = val;
    if (key.trim() === "BINANCE_SECRET_KEY") SECRET_KEY = val;
  }
} catch { console.error("Failed to read .env"); }

if (!API_KEY || !SECRET_KEY) {
  console.error("BINANCE_API_KEY or BINANCE_SECRET_KEY missing from .env");
  process.exit(1);
}

const BINANCE_BASE = "https://api.binance.com";

function sign(queryString) {
  return createHmac("sha256", SECRET_KEY).update(queryString).digest("hex");
}

async function binanceRequest(path, params = {}) {
  params.timestamp = Date.now().toString();
  params.recvWindow = "10000";
  const qs = new URLSearchParams(params).toString();
  const signature = sign(qs);
  const url = `${BINANCE_BASE}${path}?${qs}&signature=${signature}`;

  const res = await fetch(url, {
    headers: { "X-MBX-APIKEY": API_KEY },
  });
  return { status: res.status, data: await res.json() };
}

async function binancePublic(path, params = {}) {
  const qs = new URLSearchParams(params).toString();
  const url = `${BINANCE_BASE}${path}${qs ? `?${qs}` : ""}`;
  const res = await fetch(url);
  return { status: res.status, data: await res.json() };
}

const PORT = 3001;

createServer(async (req, res) => {
  // CORS
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }

  const url = new URL(req.url, `http://localhost:${PORT}`);
  const path = url.pathname;

  try {
    // GET /account — full account info with balances
    if (path === "/account") {
      const { status, data } = await binanceRequest("/api/v3/account");
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    }

    // GET /balances — filtered non-zero balances
    else if (path === "/balances") {
      const { data } = await binanceRequest("/api/v3/account");
      const balances = (data.balances || [])
        .map((b) => ({ asset: b.asset, free: parseFloat(b.free), locked: parseFloat(b.locked) }))
        .filter((b) => b.free > 0 || b.locked > 0);
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify(balances));
    }

    // GET /ticker?symbol=BTCUSDT — current price
    else if (path === "/ticker") {
      const symbol = url.searchParams.get("symbol") || "BTCUSDT";
      const { status, data } = await binancePublic("/api/v3/ticker/24hr", { symbol });
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    }

    // POST /order — place a real order
    else if (path === "/order" && req.method === "POST") {
      let body = "";
      for await (const chunk of req) body += chunk;
      const params = JSON.parse(body);
      // Required: symbol, side, type, quantity (or quoteOrderQty)
      if (!params.symbol || !params.side || !params.type) {
        res.writeHead(400, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Missing required fields: symbol, side, type" }));
        return;
      }
      const { status, data } = await binanceRequest("/api/v3/order", params);
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    }

    // GET /orders?symbol=BTCUSDT — open orders
    else if (path === "/orders") {
      const symbol = url.searchParams.get("symbol");
      const params = symbol ? { symbol } : {};
      const { status, data } = await binanceRequest("/api/v3/openOrders", params);
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    }

    // GET /trades?symbol=BTCUSDT — recent trades
    else if (path === "/trades") {
      const symbol = url.searchParams.get("symbol") || "BTCUSDT";
      const { status, data } = await binanceRequest("/api/v3/myTrades", { symbol, limit: "20" });
      res.writeHead(status, { "Content-Type": "application/json" });
      res.end(JSON.stringify(data));
    }

    // Health check
    else if (path === "/health") {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ status: "ok", connected: !!API_KEY }));
    }

    else {
      res.writeHead(404, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: "Not found" }));
    }
  } catch (err) {
    res.writeHead(500, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: err.message }));
  }
}).listen(PORT, () => {
  console.log(`Binance proxy running on http://localhost:${PORT}`);
  console.log(`API Key: ${API_KEY.slice(0, 8)}...${API_KEY.slice(-4)}`);
});
