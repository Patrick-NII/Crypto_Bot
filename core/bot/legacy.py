# gluetrade_bot.py
import os
import json
from datetime import datetime
from dotenv import load_dotenv
import requests

from modules.fetch_crypto import get_crypto_data
from modules.fetch_stocks import get_stock_data
from modules.utils import format_currency, log_report

load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Données Crypto
crypto_report, total_crypto = get_crypto_data()
crypto_lines = [
    f"- {name} : {format_currency(value)} ({amount} @ {format_currency(price)})"
    for name, amount, price, value in crypto_report
]

# Données PEA
pea_report, total_pea = get_stock_data("data/wallet_pea.json")
pea_lines = [
    f"- {ticker} : {format_currency(value)} (PRU {format_currency(pru)} / Gain: {format_currency(gain)})"
    for ticker, amount, price, value, pru, gain in pea_report
]
total_pea_loss = sum([gain for _, _, _, _, _, gain in pea_report])

# Données Actions
stocks_report, total_stocks = get_stock_data("data/wallet_actions.json")
stocks_lines = [
    f"- {ticker} : {format_currency(value)} (PRU {format_currency(pru)} / Gain: {format_currency(gain)})"
    for ticker, amount, price, value, pru, gain in stocks_report
]

# Rapport
now = datetime.now().strftime("%d/%m/%Y %H:%M")
message = f"""Bonjour M. NII, voici le point sur vos investissements ({now}).

📊 PERTES TOTALES ACTUELLES (PEA) : {format_currency(total_pea_loss)}

═════════════════
🔹 CRYPTO (Revolut)
{chr(10).join(crypto_lines)}

➡️ Total crypto : {format_currency(total_crypto)} | Tendance : {'↗️' if total_crypto > 2500 else '↘️'}

═════════════════
🔹 PEA (Fortuneo)
{chr(10).join(pea_lines)}

➡️ Total PEA : {format_currency(total_pea)} | Tendance : {'↘️ Négative' if total_pea_loss < 0 else '↗️ Positive'}

═════════════════
🔹 ACTIONS (Revolut)
{chr(10).join(stocks_lines)}

➡️ Total actions : {format_currency(total_stocks)} | Tendance : {'↗️ Forte' if total_stocks > 150 else '↔️ Stable'}

📈 Projection fin 2025 (hypothèse +10 %/an) :
Portefeuille total ≈ {format_currency((total_crypto + total_pea + total_stocks) * 1.1)}

Prochain point dans 15 min."""

# Envoi
res = requests.post(
    f"https://api.telegram.org/bot{TOKEN}/sendMessage",
    data={"chat_id": CHAT_ID, "text": message}
)
print("Statut :", res.status_code)
print("Réponse :", res.json())
log_report(message)
