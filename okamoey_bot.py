import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CRYPTO_HOLDINGS = {
    "bitcoin": 0.014,
    "render-token": 103.28,
    "ethereum": 0.11,
    "solana": 2,
    "fetch-ai": 327.29,
    "arbitrum": 417.97,
    "avalanche-2": 7.57
}

def format_currency(value):
    return f"{value:,.2f} €".replace(",", " ").replace(".", ",")

def get_crypto_prices():
    ids = ",".join(CRYPTO_HOLDINGS.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur"
    res = requests.get(url)
    return res.json()

def send_report():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    prices = get_crypto_prices()

    total_crypto_value = 0
    crypto_lines = []

    for token_id, amount in CRYPTO_HOLDINGS.items():
        if token_id in prices:
            price = prices[token_id]["eur"]
            total = amount * price
            total_crypto_value += total
            name = token_id.replace("-", " ").title()
            crypto_lines.append(f"- {name} : {format_currency(total)} ({amount} @ {format_currency(price)})")

    # Données fixes pour actions (à remplacer ensuite par yfinance ou RapidAPI)
    pea = {
        "Cavendish Hydrogen": (619.40, -412.60),
        "Europlasma": (2.39, -2822.51),
        "Navya": (0.09, -35.98),
        "NEL ASA": (1443.99, -1997.08)
    }

    stocks = {
        "X-FAB": (174.79, 16.53)
    }

    total_pea = sum([val[0] for val in pea.values()])
    total_stocks = sum([val[0] for val in stocks.values()])
    total_loss = sum([val[1] for val in pea.values()])

    message = f"""Bonjour M. Ngunga, voici le point sur vos investissements ({now}).

📊 PERTES TOTALES ACTUELLES : {format_currency(total_loss)}

══════════════════════
🔹 CRYPTO (Revolut)
""" + "\n".join(crypto_lines) + f"""

➡️ Total crypto : {format_currency(total_crypto_value)} | Tendance : {'↗️' if total_crypto_value > 2500 else '↘️'}

══════════════════════
🔹 PEA (Fortuneo)
""" + "\n".join([
        f"- {k} : {format_currency(v[0])} ({format_currency(v[1])})"
        for k, v in pea.items()
    ]) + f"""

➡️ Total PEA : {format_currency(total_pea)} | Tendance : {'↘️ Négative' if total_loss < 0 else '↗️ Positive'}

══════════════════════
🔹 ACTIONS (Revolut)
""" + "\n".join([
        f"- {k} : {format_currency(v[0])} (+{v[1]} %)"
        for k, v in stocks.items()
    ]) + f"""

➡️ Total actions : {format_currency(total_stocks)} | Tendance : {'↗️ Forte' if list(stocks.values())[0][1] > 5 else '↔️ Stable'}

📈 Projection fin 2025 (hypothèse +10 %/an) :
Portefeuille total ≈ {format_currency((total_crypto_value + total_pea + total_stocks) * 1.1)}

Prochain point dans 15 min."""

    res = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": message}
    )
    print("Statut :", res.status_code)
    print("Réponse :", res.json())

send_report()