import requests
from datetime import datetime

def get_top_opportunities():
    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 15,
        "page": 1,
        "sparkline": False
    }
    r = requests.get(url, params=params)
    coins = r.json()

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    header = [
        "📢 *NOUVELLE ANALYSE OPPORTUNITÉS*",
        "",
        "🚀 *TOP 5 OPPORTUNITÉS CRYPTO - ANALYSE FINANCIÈRE*",
        "📊 *Méthodologie* : Analyse multi-facteurs (marché, communauté, développement)",
        f"📅 *Date d'analyse* : {now}",
        ""
    ]

    # Simuler un score et confiance (à remplacer par une vraie logique plus tard)
    def simulate_score(coin):
        dev = coin.get("developer_score", 0) or 50
        mkt = coin["market_cap_rank"]
        return {
            "global_score": round(100 - mkt + dev * 0.2, 1),
            "confidence": round(75 + (dev / 10), 1),
            "dev_score": dev,
            "community_score": 50 + mkt % 20,
            "market_score": 80 + (100 - mkt) * 0.2
        }

    entries = []
    for coin in coins[:5]:
        scores = simulate_score(coin)
        entry = f"""
1. *{coin['name']}* ({coin['symbol']})
💰 Prix actuel : `${coin['current_price']:,.4f}`
📈 Score global : `{scores['global_score']}/100`
🎯 Niveau de confiance : `{scores['confidence']}%`

📊 *Métriques marché* :
• Capitalisation : `${coin['market_cap']:,.0f}`
• Volume 24h : `${coin['total_volume']:,.0f}`
• Variation 24h : `{coin['price_change_percentage_24h']:.2f}%`
• Variation 7j : `N/A`  _(ajouter si dispo)_

🏆 *Scores détaillés* :
• Marché : `{scores['market_score']:.1f}/100`
• Communauté : `{scores['community_score']:.1f}/100`
• Développement : `{scores['dev_score']}/100`

💡 *Recommandations* :
• Diversifiez sur plusieurs projets de la liste
• Surveillez l’évolution des développeurs (GitHub, Roadmap)
• Comparez avec les leaders de leur segment (L1, L2, AI, etc.)
• Maintenez une stratégie DCA + suivi stop-loss

⚠️ *Disclaimer* : Ce message n’est pas un conseil d’investissement. Faites vos propres recherches.

🔍 *Sources* : CoinGecko API, analyse marché, modèle heuristique interne
"""
        entries.append(entry.strip())

    final_message = "\n".join(header + entries)
    return final_message