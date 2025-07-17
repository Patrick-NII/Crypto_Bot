import os
import requests
from openai import OpenAI
from datetime import datetime
from dotenv import load_dotenv

# Load credentials from .env
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# Setup OpenAI client (v1.0+)
client = OpenAI(api_key=OPENAI_API_KEY)

# Get top cryptos from CoinGecko
def get_top_cryptos(limit=10):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False
    }
    response = requests.get(url, params=params, timeout=10)
    return response.json()

# Format market update
def format_market_summary(cryptos):
    lines = ["📊 *MISE À JOUR MARCHÉ*\n"]
    for coin in cryptos:
        symbol = coin['symbol'].upper()
        name = coin['name']
        price = coin['current_price']
        change = coin['price_change_percentage_24h'] or 0
        emoji = "📈" if change > 0 else "📉" if change < 0 else "➖"
        lines.append(f"💰 {name} ({symbol})\n• Prix: ${price:,.2f}\n• 24h: {emoji} {change:+.2f}%\n")
    lines.append(f"⏰ {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    return "\n".join(lines)

# Get AI summary using GPT-4
def generate_ai_analysis(cryptos):
    prompt = f"""
Tu es un analyste financier expert en crypto, macro-économie et détection d'opportunités. Rédige une analyse synthétique quotidienne basée sur les données de marché ci-dessous. Utilise un ton clair, structurant et impactant. Ta mission est d'identifier les cryptomonnaies ayant un fort potentiel (nouveaux projets, niches porteuses, signaux de pump, contexte économique global).

Données du jour :
{cryptos}

Inclure :
- Salutations et présentation de l'analyse hebdomadaire
- Analyse économique et sectorielle
- Signal fort ou faiblesse pour chaque projet
- Corrélation éventuelle avec les tendances macro (inflation, IA, démographie, climat, etc.)
#- Sources potentielles : Reddit, Medium, Bloomberg, On-chain Data
- Objectif : Aider à détecter les cryptos prometteuses avant les autres.
- fuite de fin rester brancher
"""
    chat_completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Tu es un analyste financier crypto de haut niveau."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1200
    )
    return chat_completion.choices[0].message.content.strip()

# Send Telegram message
def send_to_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )

# Run full routine
try:
    cryptos = get_top_cryptos(10)
    market_summary = format_market_summary(cryptos)
    ai_analysis = generate_ai_analysis(cryptos)

    message = (
        "📢 *NOUVELLE ANALYSE OPPORTUNITÉS*\n\n"
        f"{market_summary}\n\n"
        "💡 *Analyse Okamoey :*\n"
        f"{ai_analysis}"
    )

    send_to_telegram(message)

except Exception as e:
    send_to_telegram(f"⚠️ Erreur analyse marché : {e}")