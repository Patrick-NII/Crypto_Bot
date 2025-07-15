import requests
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Simulé pour test : prix fictif
wallet = {
    "BTC": {"amount": 0.014, "price": 101000, "euro": 0.014 * 101000},
    "RNDR": {"amount": 103.28, "price": 3.29, "euro": 103.28 * 3.29},
    "ETH": {"amount": 0.1, "price": 2630, "euro": 0.1 * 2630},
}

# Génération du message "PDG-style"
message = "Bonjour Monsieur Ngunga.\nVoici l’état synthétique de vos investissements :\n\n"
total = 0

for token, data in wallet.items():
    value = round(data["euro"], 2)
    total += value
    message += f"— {token}: {value} € ({data['amount']} @ {data['price']} €)\n"

message += f"\n💼 Total actuel : {round(total, 2)} €\nSurveillance active, aucune alerte majeure à signaler."

# Envoi Telegram
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
params = {
    "chat_id": CHAT_ID,
    "text": message
}
response = requests.get(url, params=params)

print("Message envoyé :", response.status_code, response.text)