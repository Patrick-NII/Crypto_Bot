import os
import json
import requests
import matplotlib
matplotlib.use("Agg")   # backend sans écran
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from datetime import datetime, timedelta
import numpy as np
from scipy.interpolate import make_interp_spline
from collections import OrderedDict
import traceback

# ───────────────────────────────
# Initialisation
# ───────────────────────────────
load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

os.makedirs("data", exist_ok=True)
os.makedirs("charts", exist_ok=True)

def safe_send_message(msg, parse_mode="MarkdownV2"):
    """Envoi un message Telegram sécurisé"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "parse_mode": parse_mode},
            timeout=15
        )
    except Exception as e:
        print("Erreur Telegram:", e)

try:
    # ───────────────────────────────
    # Charger les transactions
    # ───────────────────────────────
    with open("data/wallet_transactions.json") as f:
        transactions = json.load(f)

    wallet_stats = {}
    for coin, txs in transactions.items():
        qty = sum(t['amount'] for t in txs)
        invested = sum(t['total'] for t in txs)
        avg_price = invested / qty if qty else 0
        wallet_stats[coin] = {"qty": qty, "invested": invested, "avg_price": avg_price}

    # ───────────────────────────────
    # Récupérer prix CoinGecko
    # ───────────────────────────────
    ids = ','.join(wallet_stats.keys())
    try:
        res = requests.get(
            f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur",
            timeout=15
        )
        res.raise_for_status()
        prices = res.json()
    except Exception as e:
        print("Erreur CoinGecko:", e)
        prices = {k: {"eur": 1} for k in wallet_stats}  # fallback

    # Abréviations
    SYMBOLS = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
        "solana": "SOL",
        "render-token": "RNDR",
        "arbitrum": "ARB",
        "fetch-ai": "FET",
        "avalanche-2": "AVAX"
    }

    # ───────────────────────────────
    # Calculs portefeuille
    # ───────────────────────────────
    wallet_perf = []
    total_value, total_fees = 0, 0
    emoji = lambda x: "▲" if x > 0 else "▼" if x < 0 else "→"

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

    # Frais totaux
    for txs in transactions.values():
        for t in txs:
            total_fees += t["fees"]
    net_value = total_value - total_fees

    # ───────────────────────────────
    # Graphique répartition portefeuille
    # ───────────────────────────────
    wallet_perf_sorted = sorted(wallet_perf, key=lambda x: x['value'])
    labels = [w['coin'] for w in wallet_perf_sorted]
    values = [w['value'] for w in wallet_perf_sorted]
    colors = ["royalblue" if w['perf'] > 0 else "red" if w['perf'] < 0 else "gray" for w in wallet_perf_sorted]
    percentages = [v / total_value * 100 for v in values]

    plt.figure(figsize=(10, 8))
    bars = plt.barh(labels, values, color=colors)
    for i, bar in enumerate(bars):
        width = bar.get_width()
        plt.text(width + total_value * 0.01, bar.get_y() + bar.get_height()/2,
                 f"{values[i]:.2f} € | {percentages[i]:.1f} %",
                 va='center', fontsize=10, fontweight='bold')
    plt.title("Répartition du portefeuille", fontsize=14, fontweight='bold', pad=15)
    plt.tight_layout()
    plt.savefig("charts/wallet_1.png", dpi=300, bbox_inches="tight")
    plt.close()

    # ───────────────────────────────
    # Historique Net (net_history.json)
    # ───────────────────────────────
    history_file = "data/net_history.json"
    if os.path.exists(history_file):
        with open(history_file, "r") as f:
            net_history = json.load(f)
    else:
        net_history = []

    now = datetime.now()
    should_add = True
    if net_history:
        last_ts = datetime.fromisoformat(net_history[-1]["timestamp"])
        if (now - last_ts) < timedelta(minutes=15):
            should_add = False

    if should_add:
        net_history.append({"timestamp": now.isoformat(), "net_value": round(net_value, 2)})

    net_history = net_history[-12:]
    if should_add:
        with open(history_file, "w") as f:
            json.dump(net_history, f, indent=2)

    # Graphique évolution Net
    grouped = OrderedDict()
    for entry in reversed(net_history):
        ts = datetime.fromisoformat(entry["timestamp"])
        rounded_min = (ts.minute // 15) * 15
        rounded_time = ts.replace(minute=rounded_min, second=0, microsecond=0)
        if rounded_time not in grouped:
            grouped[rounded_time] = entry["net_value"]

    timestamps = list(sorted(grouped.keys()))
    values = [grouped[t] for t in timestamps]

    plt.figure(figsize=(10, 6))
    if len(values) >= 4:
        x = np.linspace(0, len(values) - 1, 300)
        spl = make_interp_spline(range(len(values)), values, k=3)
        y_smooth = spl(x)
        plt.plot(x, y_smooth, color="royalblue", linewidth=3.5)
    else:
        plt.plot(range(len(values)), values, color="royalblue", linewidth=3.5)

    plt.scatter(range(len(values)), values, color="royalblue", zorder=5)
    xtick_labels = [t.strftime('%H:%M') for t in timestamps]
    plt.xticks(ticks=range(len(values)), labels=xtick_labels, fontsize=12)
    for i, v in enumerate(values):
        plt.annotate(f"{v:.0f}€", (i, v), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=12)

    plt.title("Évolution du Net (6 dernières heures)", fontsize=13, fontweight='bold', pad=10)
    plt.tight_layout()
    plt.savefig("charts/net_value.png", dpi=300)
    plt.close()

    # ───────────────────────────────
    # Envoi images
    # ───────────────────────────────
    for img_file in ["charts/wallet_1.png", "charts/net_value.png"]:
        if os.path.exists(img_file):
            with open(img_file, "rb") as img:
                requests.post(
                    f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
                    data={"chat_id": CHAT_ID},
                    files={"photo": img},
                    timeout=20
                )

    # ───────────────────────────────
    # Envoi rapport texte
    # ───────────────────────────────
    def format_valeur(v):
        return f"{v/1000:.2f}k€" if v >= 1000 else f"{v:.2f}€"

    now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
    lines = [
        f"📄 Rapport — {now_str}",
        f"*Total brut* : {total_value:,.2f} €",
        f"*Frais cumulés* : {total_fees:,.2f} €",
        f"*Net estimé* : {net_value:,.2f} €",
        "",
        "Sym  Qté    Valeur    ±€   Taux",
        "```"
    ]
    for w in sorted(wallet_perf, key=lambda x: -x['value']):
        sym = w['coin']
        qty = f"{w['qty']:>6.2f}"
        val = format_valeur(w['value']).rjust(7)
        perf = f"{w['perf']:+.0f}€".rjust(5)
        pct = f"{w['pct']:+.0f}% {w['emoji']}".rjust(6)
        lines.append(f"{sym:<4} {qty}  {val}  {perf}  {pct}")
    lines.append("```")
    text = "\n".join(lines)

    # Échapper MarkdownV2
    for ch in ["-", ".", "(", ")", "€"]:
        text = text.replace(ch, f"\\{ch}")

    safe_send_message(text, parse_mode="MarkdownV2")

except Exception:
    err = traceback.format_exc()
    safe_send_message(f"❌ Crash info_wallet.py\n```\n{err}\n```", parse_mode="Markdown")