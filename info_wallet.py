import os
import json
import requests
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from datetime import datetime, timedelta
import numpy as np
from scipy.interpolate import make_interp_spline
from collections import OrderedDict

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
    prices = {k: {"eur": 1} for k in wallet_stats}  # fallback temporaire

# Abréviations personnalisées
SYMBOLS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "render-token": "RNDR",
    "arbitrum": "ARB",
    "fetch-ai": "FET",
    "avalanche-2": "AVAX"
}

# Calcul performance
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
        "coin": SYMBOLS.get(coin, coin[:6].upper()),  # Nom abrégé ou fallback
        "qty": stat["qty"],
        "price": price,
        "value": value,
        "avg": stat["avg_price"],
        "invested": stat["invested"],
        "perf": perf_eur,
        "pct": perf_pct,
        "emoji": emoji(perf_eur)
    })

# 🔢 Statistiques globales
with open("data/wallet_transactions.json") as f:
    all_tx = json.load(f)
total_fees = sum(t["fees"] for txs in all_tx.values() for t in txs)
net_value = total_value - total_fees

# Graphique matplotlib (version pro)
wallet_perf_sorted = sorted(wallet_perf, key=lambda x: x['value'])
labels = [w['coin'] for w in wallet_perf_sorted]
values = [w['value'] for w in wallet_perf_sorted]
colors = ["royalblue" if w['perf'] > 0 else "red" if w['perf'] < 0 else "gray" for w in wallet_perf_sorted]
percentages = [v / total_value * 100 for v in values]


import numpy as np
from scipy.interpolate import make_interp_spline

# ➕ Log de net_value
history_file = "data/net_history.json"

# Charger l'historique si existant
if os.path.exists(history_file):
    with open(history_file, "r") as f:
        net_history = json.load(f)
else:
    net_history = []

# Ajouter la nouvelle entrée
now_iso = datetime.now().isoformat()
net_history.append({"timestamp": now_iso, "net_value": round(net_value, 2)})

# Garder les 12 dernières entrées (6h à raison d'une entrée/30min)
net_history = net_history[-12:]

# Sauvegarder l'historique
with open(history_file, "w") as f:
    json.dump(net_history, f, indent=2)


plt.figure(figsize=(10, 8))
bars = plt.barh(labels, values, color=colors)

# Ajouter le texte (valeur en € + pourcentage) à droite de chaque barre
for i, bar in enumerate(bars):
    width = bar.get_width()
    plt.text(width + total_value * 0.01, bar.get_y() + bar.get_height()/2,
             f"{values[i]:.2f} € | {percentages[i]:.1f} %",
             va='center', fontsize=10, fontweight='bold')

# Nettoyage de l'axe et du cadre
plt.gca().spines['top'].set_visible(False)
plt.gca().spines['right'].set_visible(False)
plt.gca().spines['bottom'].set_visible(False)
plt.gca().spines['left'].set_visible(False)
plt.tick_params(axis='x', which='both', bottom=False, top=False, labelbottom=False)
plt.tick_params(axis='y', labelsize=11)

plt.title("Répartition du portefeuille", fontsize=14, fontweight='bold', pad=15)
plt.tight_layout()
plt.savefig(f"/Users/nii/Documents/Crypto_Bot/charts/wallet_1.png", dpi=300, bbox_inches="tight")
plt.close()




# ➕ Graphique évolution Net
history_file = "data/net_history.json"
chart_path = "charts/net_value.png"

# Charger historique
if os.path.exists(history_file):
    with open(history_file, "r") as f:
        net_history = json.load(f)
else:
    net_history = []

# Obtenir le timestamp actuel
now = datetime.now()
should_add = True

# Vérification si la dernière entrée est trop récente (< 15 minutes)
if net_history:
    last_ts = datetime.fromisoformat(net_history[-1]["timestamp"])
    delta = now - last_ts
    if delta < timedelta(minutes=15):
        should_add = False

# Ajouter si respect du délai
if should_add:
    net_history.append({
        "timestamp": now.isoformat(),
        "net_value": round(net_value, 2)
    })

# Garder les 12 dernières entrées
net_history = net_history[-12:]

# Sauvegarder uniquement si ajout autorisé
if should_add:
    os.makedirs(os.path.dirname(history_file), exist_ok=True)
    with open(history_file, "w") as f:
        json.dump(net_history, f, indent=2)




from collections import OrderedDict

# Grouper les points par tranche de 15 minutes, garder le dernier
grouped = OrderedDict()
for entry in reversed(net_history):
    ts = datetime.fromisoformat(entry["timestamp"])
    rounded_min = (ts.minute // 15) * 15
    rounded_time = ts.replace(minute=rounded_min, second=0, microsecond=0)
    if rounded_time not in grouped:
        grouped[rounded_time] = entry["net_value"]

# Extraire les données
timestamps = list(sorted(grouped.keys()))
values = [grouped[t] for t in timestamps]

plt.figure(figsize=(10, 6))

if len(values) >= 4:
    # Courbe lissée avec spline
    x = np.linspace(0, len(values) - 1, 300)
    spl = make_interp_spline(range(len(values)), values, k=3)
    y_smooth = spl(x)
    plt.plot(x, y_smooth, color="royalblue", linewidth=3.5)
else:
    # Trop peu de points → courbe directe
    plt.plot(range(len(values)), values, color="royalblue", linewidth=3.5)

# Points et annotations
plt.scatter(range(len(values)), values, color="royalblue", zorder=5)
xtick_labels = [t.strftime('%H:%M') for t in timestamps]
plt.xticks(ticks=range(len(values)), labels=xtick_labels, rotation=0, fontsize=12)

for i, v in enumerate(values):
    plt.annotate(f"{v:.0f}€", (i, v), textcoords="offset points", xytext=(0, 10), ha='center', fontsize=12)

# Style
plt.gca().spines[['top', 'right', 'left']].set_visible(False)
plt.tick_params(axis='y', left=False, labelleft=False)
plt.title("Évolution du Net (6 dernières heures)", fontsize=13, fontweight='bold', pad=10)
plt.tight_layout()
plt.savefig(chart_path, dpi=300)
plt.close()

# Envoi image
i = 0
while True:
    image_path = f"/Users/nii/Documents/Crypto_Bot/charts/wallet_{i+1}.png"
    if not os.path.exists(image_path):
        break  # Arrête la boucle dès qu'un fichier est introuvable
    with open(image_path, "rb") as img:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID},
            files={"photo": img}
        )
    i += 1

# Envoi du graphique net_value séparément
net_chart = "/Users/nii/Documents/Crypto_Bot/charts/net_value.png"
if os.path.exists(net_chart):
    with open(net_chart, "rb") as img:
        requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendPhoto",
            data={"chat_id": CHAT_ID},
            files={"photo": img}
        )






# Fonction pour format compact
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


# Envoi message texte
requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
)