import os
import json
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from dotenv import load_dotenv

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

# Calcul performance
wallet_perf = []
total_value = 0
emoji = lambda x: "📈" if x > 0 else "📉" if x < 0 else "⚖️"

for coin, stat in wallet_stats.items():
    price = prices.get(coin, {}).get("eur", 0)
    value = stat["qty"] * price
    perf_eur = value - stat["invested"]
    perf_pct = ((price - stat["avg_price"]) / stat["avg_price"]) * 100 if stat["avg_price"] else 0
    total_value += value
    wallet_perf.append({
        "coin": coin.upper(),
        "qty": stat["qty"],
        "price": price,
        "value": value,
        "avg": stat["avg_price"],
        "invested": stat["invested"],
        "perf": perf_eur,
        "pct": perf_pct,
        "emoji": emoji(perf_eur)
    })

# Message Telegram texte
now = datetime.now().strftime("%d/%m/%Y %H:%M")
lines = [f"📊 *Rapport de Performance* — `{now}`", f"💰 *Valeur totale* : `{total_value:,.2f} €`", "", "*Détail par crypto :*",
         "`🪙 Crypto    Qté     Prix     Valeur     Achat     +/- €     %    `"]
lines.append("```")
for w in wallet_perf:
    lines.append(f"{w['coin']:<10} {w['qty']:>6.4f} {w['price']:>8.2f} {w['value']:>9.2f} {w['avg']:>9.2f} {w['perf']:>8.2f} {w['pct']:>6.2f}% {w['emoji']}")
lines.append("```")
text = "\n".join(lines)

# Envoi message texte
requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
)

# Graphique matplotlib (version pro)
wallet_perf_sorted = sorted(wallet_perf, key=lambda x: x['value'])
labels = [w['coin'] for w in wallet_perf_sorted]
values = [w['value'] for w in wallet_perf_sorted]
colors = ["royalblue" if w['perf'] > 0 else "red" if w['perf'] < 0 else "gray" for w in wallet_perf_sorted]
percentages = [v / total_value * 100 for v in values]

plt.figure(figsize=(10, 6))
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