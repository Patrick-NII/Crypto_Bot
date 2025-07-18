import os
import requests
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI

# Chargement des variables d'environnement
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

client = OpenAI(api_key=OPENAI_API_KEY)

# Fonction : Top cryptos (on prendra seulement hors top 10)
def get_top_cryptos(limit=50):
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": limit,
        "page": 1,
        "sparkline": False
    }
    r = requests.get(url, params=params, timeout=10)
    return r.json()

# Analyse GPT-4
def generate_ai_analysis(cryptos):
    prompt = f"""
Tu es un analyste financier spécialisé en crypto et macro-économie.
Écris une analyse structurée sur ces projets prometteurs (hors top 10 capitalisation).
Inclure tendances macro, signaux faibles/forts, recommandations et domaines porteurs (IA, blockchain, etc.).

Données CoinGecko :
{cryptos}
"""
    completion = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Tu es un expert en analyse de marché crypto."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1200
    )
    return completion.choices[0].message.content.strip()

# Envoi Telegram
def send_to_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )

# Détection opportunités hors top 10
def get_opportunities():
    coins = get_top_cryptos(50)
    altcoins = [c for c in coins if c["market_cap_rank"] > 10][:20]

    def simulate_score(coin):
        vol = coin.get("total_volume", 0)
        dev_score = coin.get("developer_score", 50)
        market_score = max(0, 100 - coin["market_cap_rank"] * 0.8)
        score = 0.4 * market_score + 0.3 * dev_score + 0.3 * min(vol / 1_000_000, 100)
        return round(score, 1)

    sorted_altcoins = sorted(altcoins, key=simulate_score, reverse=True)[:10]
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    header = [
        "📢 *NOUVELLE ANALYSE OPPORTUNITÉS*",
        "",
        "🚀 *TOP 10 CHALLENGERS HORS TOP 10 CAPITALISATION*",
        "📊 Méthodologie : Score basé sur volume, dev et rang marché",
        f"🕒 Analyse du {now}",
        ""
    ]

    body = []
    for i, coin in enumerate(sorted_altcoins, 1):
        price = f"${coin['current_price']:,.4f}"
        change = coin["price_change_percentage_24h"] or 0
        score = simulate_score(coin)
        body.append(
            f"""{i}. *{coin['name']}* ({coin['symbol']})
💰 Prix : `{price}` | 24h : `{change:+.2f}%`
📈 Score : `{score}/100`
📊 MarketCap : `${coin['market_cap']:,.0f}`
🔁 Volume 24h : `${coin['total_volume']:,.0f}`
"""
        )

    return "\n".join(header + body)

# Routine principale
try:
    cryptos = get_top_cryptos()
    ai = generate_ai_analysis(cryptos)
    opportunities = get_opportunities()

    full_message = (
        "📊 *RAPPORT OKAMOEY - CHALLENGERS DU MARCHÉ*\n\n"
        f"{ai}\n\n"
        f"{opportunities}"
    )

    send_to_telegram(full_message)

except Exception as e:
    send_to_telegram(f"⚠️ Erreur dans le script : {e}")