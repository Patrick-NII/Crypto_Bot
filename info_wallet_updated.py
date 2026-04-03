
import os
import json
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv
import numpy as np
from scipy.interpolate import make_interp_spline

# Chargement .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Charger les transactions
with open("data/wallet_transactions.json") as f:
    transactions = json.load(f)

# Statistiques portefeuille
wallet_stats = {}
for coin, txs in transactions.items():
    qty = sum(t['amount'] for t in txs)
    invested = sum(t['total'] for t in txs)
    avg_price = invested / qty if qty else 0
    wallet_stats[coin] = {"qty": qty, "invested": invested, "avg_price": avg_price}

# Prix depuis CoinGecko
ids = ','.join(wallet_stats.keys())
try:
    res = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur")
    prices = res.json()
except:
    prices = {k: {"eur": 1} for k in wallet_stats}

SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "render-token": "RNDR",
    "arbitrum": "ARB",
    "fetch-ai": "FET",
    "avalanche-2": "AVAX"
}

wallet_perf = []
total_value = 0
emoji = lambda x: "▲" if x > 0 else "▼" if x < 0 else "●"

for coin, stat in wallet_stats.items():
    price = prices.get(coin, {}).get("eur", 0)
    value = stat["qty"] * price
    perf_eur = value - stat["invested"]
    perf_pct = ((price - stat["avg_price"]) / stat["avg_price"]) * 100 if stat["avg_price"] else 0
    total_value += value
    wallet_perf.append({
        "coin": SYMBOLS.get(coin, coin[:6].upper()),
        "qty": stat["qty"],
        "price": price,
        "value": value,
        "avg": stat["avg_price"],
        "invested": stat["invested"],
        "perf": perf_eur,
        "pct": perf_pct,
        "emoji": emoji(perf_eur)
    })

with open("data/wallet_transactions.json") as f:
    all_tx = json.load(f)
total_fees = sum(t["fees"] for txs in all_tx.values() for t in txs)
net_value = total_value - total_fees

def format_valeur(v):
    return f"{v/1000:.2f}k€" if v >= 1000 else f"{v:.2f}€"

now = datetime.now().strftime("%d/%m/%Y %H:%M")
lines = [
    f"📄 Rapport — `{now}`",
    f"*Total brut* : `{total_value:,.2f} €`",
    f"*Frais cumulés* : `{total_fees:,.2f} €`",
    f"*Net estimé* : `{net_value:,.2f} €`",
    "",
    "`Sym  Qté    Valeur  ± €   Taux `",
    "```"
]

for w in sorted(wallet_perf, key=lambda x: -x['value']):
    sym = w['coin'][:4].upper()
    qty = f"{w['qty']:>6.2f}"
    val = format_valeur(w['value']).rjust(7)
    perf = f"{w['perf']:+.0f}€".rjust(5)
    pct = f"{w['pct']:+.0f}% {'▲' if w['pct'] > 0 else '▼' if w['pct'] < 0 else '→'}".rjust(6)
    lines.append(f"{sym:<4} {qty}  {val}  {perf}  {pct}")

lines.append("```")
text = "\n".join(lines)

requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
)

# ➕ Graphique évolution Net
history_file = "data/net_history.json"
chart_path = "charts/net_value.png"

if os.path.exists(history_file):
    with open(history_file, "r") as f:
        net_history = json.load(f)
else:
    net_history = []

now = datetime.now()
net_history.append({"timestamp": now.isoformat(), "net_value": round(net_value, 2)})
net_history = net_history[-12:]

os.makedirs(os.path.dirname(history_file), exist_ok=True)
with open(history_file, "w") as f:
    json.dump(net_history, f, indent=2)

timestamps = [datetime.fromisoformat(p["timestamp"]) for p in net_history]
values = [p["net_value"] for p in net_history]

x = np.linspace(0, len(values) - 1, 300)
spl = make_interp_spline(range(len(values)), values, k=3)
y_smooth = spl(x)

xticks = range(len(values))
xtick_labels = [t.strftime('%H:%M') for t in timestamps]

plt.figure(figsize=(10, 4))
plt.plot(x, y_smooth, color="royalblue", linewidth=2.5)
plt.scatter(xticks, values, color="royalblue", zorder=5)

plt.gca().spines[['top', 'right', 'left']].set_visible(False)
plt.tick_params(axis='y', left=False, labelleft=False)
plt.xticks(ticks=xticks, labels=xtick_labels, rotation=0, fontsize=10)

for i, v in enumerate(values):
    plt.text(i, v + max(values)*0.015, f"{v:.0f}€", fontsize=10, ha="center", va="bottom", color="black")

plt.title("Évolution du Net (6 dernières heures)", fontsize=13, fontweight='bold', pad=10)
plt.tight_layout()
os.makedirs(os.path.dirname(chart_path), exist_ok=True)
plt.savefig(chart_path, dpi=300)
plt.close()

if os.path.exists(chart_path):
    with open(chart_path, "rb") as img:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID},
            files={"photo": img}
        )
