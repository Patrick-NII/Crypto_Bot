#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de surveillance simplifié pour GlueTrade
Peut être lancé manuellement ou via cron
"""

import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Configuration de base
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/monitoring.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def send_telegram_message(message: str):
    """Envoie un message Telegram"""
    try:
        import requests
        
        # Charger les variables d'environnement
        from dotenv import load_dotenv
        load_dotenv()
        
        token = os.getenv('TOKEN')
        channel_id = os.getenv('CHAT_ID')
        
        if not token or not channel_id:
            logger.error("Token ou Channel ID manquant")
            return False
        
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = {
            'chat_id': channel_id,
            'text': message,
            'parse_mode': 'Markdown'
        }
        
        response = requests.post(url, data=data, timeout=10)
        
        if response.status_code == 200:
            logger.info("✅ Message envoyé avec succès")
            return True
        else:
            logger.error(f"❌ Erreur envoi message: {response.status_code}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Erreur envoi Telegram: {e}")
        return False

def get_crypto_data(crypto_id: str):
    """Récupère les données d'une crypto"""
    try:
        import requests
        
        url = f"https://api.coingecko.com/api/v3/coins/{crypto_id}"
        params = {
            'localization': 'false',
            'tickers': 'false',
            'market_data': 'true',
            'community_data': 'false',
            'developer_data': 'false',
            'sparkline': 'false'
        }
        
        response = requests.get(url, params=params, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
            
    except Exception as e:
        logger.error(f"Erreur récupération données {crypto_id}: {e}")
        return None

def analyze_crypto_opportunities():
    """Analyse les opportunités crypto"""
    try:
        logger.info("🚀 Démarrage analyse opportunités...")
        
        # Liste des crypto prioritaires
        crypto_list = [
            "bitcoin", "ethereum", "binancecoin", "solana", "cardano",
            "polkadot", "chainlink", "polygon", "avalanche-2", "cosmos"
        ]
        
        opportunities = []
        
        for crypto_id in crypto_list:
            try:
                data = get_crypto_data(crypto_id)
                if not data:
                    continue
                
                market_data = data.get('market_data', {})
                
                # Calculer un score simple
                price_change_24h = market_data.get('price_change_percentage_24h', 0)
                price_change_7d = market_data.get('price_change_percentage_7d', 0)
                market_cap = market_data.get('market_cap', {}).get('usd', 0)
                volume_24h = market_data.get('total_volume', {}).get('usd', 0)
                
                # Score basé sur la performance et la taille
                score = 0
                if price_change_24h > 0:
                    score += 20
                if price_change_7d > 0:
                    score += 20
                if market_cap > 1000000000:  # > 1B
                    score += 30
                if volume_24h > 10000000:  # > 10M
                    score += 30
                
                if score >= 60:  # Seuil minimum
                    opportunities.append({
                        'name': data.get('name', crypto_id),
                        'symbol': data.get('symbol', crypto_id.upper()),
                        'price': market_data.get('current_price', {}).get('usd', 0),
                        'change_24h': price_change_24h,
                        'change_7d': price_change_7d,
                        'market_cap': market_cap,
                        'score': score
                    })
                
                # Pause pour éviter de surcharger l'API
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erreur analyse {crypto_id}: {e}")
                continue
        
        # Trier par score
        opportunities.sort(key=lambda x: x['score'], reverse=True)
        
        # Générer le rapport
        if opportunities:
            report = f"""🚀 **OPPORTUNITÉS CRYPTO DÉTECTÉES**

📅 **Date d'analyse:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

"""
            
            for i, opp in enumerate(opportunities[:5], 1):
                direction_24h = "📈" if opp['change_24h'] > 0 else "📉"
                direction_7d = "📈" if opp['change_7d'] > 0 else "📉"
                
                report += f"""**{i}. {opp['name']} ({opp['symbol']})**
💰 Prix: ${opp['price']:,.4f}
📊 Score: {opp['score']}/100
📈 24h: {direction_24h} {opp['change_24h']:+.2f}%
📈 7j: {direction_7d} {opp['change_7d']:+.2f}%
💎 Market Cap: ${opp['market_cap']:,.0f}

"""
            
            report += """💡 **Recommandations:**
• Diversifiez sur plusieurs crypto
• Surveillez les volumes
• Maintenez une stratégie de DCA

⚠️ **Avertissement:** Cette analyse ne constitue pas un conseil financier."""
            
            # Envoyer le rapport
            send_telegram_message(report)
            
            logger.info(f"✅ {len(opportunities)} opportunités trouvées")
        else:
            logger.info("ℹ️ Aucune opportunité trouvée")
            
    except Exception as e:
        logger.error(f"❌ Erreur analyse opportunités: {e}")

def send_market_update():
    """Envoie une mise à jour de marché"""
    try:
        logger.info("📊 Démarrage mise à jour marché...")
        
        # Analyser Bitcoin et Ethereum
        btc_data = get_crypto_data("bitcoin")
        eth_data = get_crypto_data("ethereum")
        
        if btc_data and eth_data:
            btc_market = btc_data.get('market_data', {})
            eth_market = eth_data.get('market_data', {})
            
            btc_change = btc_market.get('price_change_percentage_24h', 0)
            eth_change = eth_market.get('price_change_percentage_24h', 0)
            
            btc_direction = "📈" if btc_change > 0 else "📉"
            eth_direction = "📈" if eth_change > 0 else "📉"
            
            message = f"""📊 **MISE À JOUR MARCHÉ**

💰 **Bitcoin (BTC)**
• Prix: ${btc_market.get('current_price', {}).get('usd', 0):,.2f}
• 24h: {btc_direction} {btc_change:+.2f}%

💰 **Ethereum (ETH)**
• Prix: ${eth_market.get('current_price', {}).get('usd', 0):,.2f}
• 24h: {eth_direction} {eth_change:+.2f}%

⏰ *{datetime.now().strftime('%d/%m/%Y %H:%M')}*"""
            
            send_telegram_message(message)
            logger.info("✅ Mise à jour marché envoyée")
            
    except Exception as e:
        logger.error(f"❌ Erreur mise à jour marché: {e}")

def main():
    """Fonction principale"""
    try:
        # Créer le répertoire logs s'il n'existe pas
        Path("logs").mkdir(exist_ok=True)
        
        # Exécuter selon les arguments
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == 'opportunities':
                analyze_crypto_opportunities()
            elif command == 'market':
                send_market_update()
            elif command == 'all':
                analyze_crypto_opportunities()
                time.sleep(5)
                send_market_update()
            else:
                print("Usage: python simple_monitor.py [opportunities|market|all]")
        else:
            # Par défaut, analyser les opportunités
            analyze_crypto_opportunities()
            
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 