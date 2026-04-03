# monitoring/cron_jobs/market_monitor.py
"""
Système de surveillance de marché en temps réel
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.config.settings import get_config
from services.crypto_analysis.market_analyzer import MarketAnalyzer
from services.notification.telegram_notifier import TelegramNotifier
from services.market_intelligence.opportunity_detector import OpportunityDetector

# Configuration
config = get_config()
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class MarketMonitor:
    """Moniteur de marché principal"""
    
    def __init__(self):
        self.market_analyzer = MarketAnalyzer()
        self.opportunity_detector = OpportunityDetector()
        self.notifier = TelegramNotifier()
        self.last_analysis = {}
        self.alert_thresholds = {
            'price_change_24h': 10.0,  # 10% de variation
            'volume_spike': 200.0,     # 200% d'augmentation volume
            'rsi_extreme': 30.0,       # RSI < 30 ou > 70
            'macd_signal': True,       # Signal MACD
            'support_resistance': 5.0  # 5% des niveaux clés
        }
    
    def run_crypto_surveillance(self):
        """Surveillance continue des crypto prioritaires"""
        try:
            logger.info("🔍 Démarrage surveillance crypto...")
            
            # Liste des crypto prioritaires
            priority_crypto = [
                "bitcoin", "ethereum", "binancecoin", "solana", "cardano",
                "polkadot", "chainlink", "polygon", "avalanche-2", "cosmos",
                "uniswap", "litecoin", "stellar", "algorand", "vechain",
                "filecoin", "tezos", "monero", "dash", "zcash"
            ]
            
            alerts = []
            
            for crypto_id in priority_crypto:
                try:
                    # Analyser la crypto
                    analysis = self.market_analyzer.analyze_crypto(crypto_id)
                    
                    if not analysis or 'error' in analysis:
                        continue
                    
                    # Vérifier les alertes
                    crypto_alerts = self._check_alerts(crypto_id, analysis)
                    alerts.extend(crypto_alerts)
                    
                    # Mettre à jour le cache
                    self.last_analysis[crypto_id] = {
                        'data': analysis,
                        'timestamp': datetime.now()
                    }
                    
                    # Pause pour éviter de surcharger l'API
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Erreur analyse {crypto_id}: {e}")
                    continue
            
            # Envoyer les alertes
            if alerts and config.ENABLE_ALERTS:
                self._send_alerts(alerts)
            
            logger.info(f"✅ Surveillance terminée - {len(alerts)} alertes détectées")
            
        except Exception as e:
            logger.error(f"❌ Erreur surveillance crypto: {e}")
    
    def run_opportunities_analysis(self):
        """Analyse des opportunités d'investissement"""
        try:
            logger.info("🚀 Démarrage analyse opportunités...")
            
            # Analyser les opportunités
            opportunities = self.opportunity_detector.find_opportunities(
                min_confidence=config.MIN_CONFIDENCE_LEVEL,
                max_results=config.MAX_OPPORTUNITIES
            )
            
            if opportunities:
                # Générer le rapport
                report = self.opportunity_detector.generate_report(opportunities)
                
                # Poster dans le canal
                if config.ENABLE_CHANNEL_POSTS:
                    self.notifier.post_to_channel(
                        f"🚀 **NOUVELLES OPPORTUNITÉS CRYPTO**\n\n{report}"
                    )
                
                logger.info(f"✅ {len(opportunities)} opportunités trouvées")
            else:
                logger.info("ℹ️ Aucune opportunité trouvée avec le niveau de confiance requis")
                
        except Exception as e:
            logger.error(f"❌ Erreur analyse opportunités: {e}")
    
    def run_market_intelligence(self):
        """Intelligence de marché et analyse sentiment"""
        try:
            logger.info("🧠 Démarrage intelligence de marché...")
            
            # Analyser le sentiment global
            sentiment = self.market_analyzer.analyze_market_sentiment()
            
            # Détecter les tendances
            trends = self.market_analyzer.detect_trends()
            
            # Générer le rapport d'intelligence
            intelligence_report = self._generate_intelligence_report(sentiment, trends)
            
            # Poster dans le canal
            if config.ENABLE_CHANNEL_POSTS:
                self.notifier.post_to_channel(intelligence_report)
            
            logger.info("✅ Intelligence de marché terminée")
            
        except Exception as e:
            logger.error(f"❌ Erreur intelligence de marché: {e}")
    
    def _check_alerts(self, crypto_id: str, analysis: dict) -> list:
        """Vérifie les conditions d'alerte pour une crypto"""
        alerts = []
        
        try:
            market_data = analysis.get('market_data', {})
            technical_data = analysis.get('technical_data', {})
            
            # Alerte variation prix 24h
            price_change = market_data.get('price_change_percentage_24h', 0)
            if abs(price_change) > self.alert_thresholds['price_change_24h']:
                direction = "📈" if price_change > 0 else "📉"
                alerts.append({
                    'type': 'price_alert',
                    'crypto': crypto_id,
                    'message': f"{direction} {crypto_id.upper()} : {price_change:+.2f}% en 24h"
                })
            
            # Alerte RSI extrême
            rsi = technical_data.get('rsi', 50)
            if rsi < 30 or rsi > 70:
                status = "survente" if rsi < 30 else "surachat"
                alerts.append({
                    'type': 'rsi_alert',
                    'crypto': crypto_id,
                    'message': f"⚠️ {crypto_id.upper()} en {status} (RSI: {rsi:.1f})"
                })
            
            # Alerte signal MACD
            macd_signal = technical_data.get('macd_signal', '')
            if macd_signal in ['buy', 'sell']:
                action = "ACHAT" if macd_signal == 'buy' else "VENTE"
                alerts.append({
                    'type': 'macd_alert',
                    'crypto': crypto_id,
                    'message': f"🎯 Signal MACD {action} pour {crypto_id.upper()}"
                })
            
        except Exception as e:
            logger.error(f"Erreur vérification alertes {crypto_id}: {e}")
        
        return alerts
    
    def _send_alerts(self, alerts: list):
        """Envoie les alertes"""
        try:
            if not alerts:
                return
            
            # Grouper les alertes par type
            alert_groups = {}
            for alert in alerts:
                alert_type = alert['type']
                if alert_type not in alert_groups:
                    alert_groups[alert_type] = []
                alert_groups[alert_type].append(alert)
            
            # Envoyer les alertes groupées
            for alert_type, type_alerts in alert_groups.items():
                if len(type_alerts) <= 3:
                    # Envoyer individuellement si peu d'alertes
                    for alert in type_alerts:
                        self.notifier.send_alert(alert['message'])
                else:
                    # Grouper si beaucoup d'alertes
                    summary = f"🚨 {len(type_alerts)} alertes {alert_type}:\n"
                    for alert in type_alerts[:5]:  # Limiter à 5
                        summary += f"• {alert['message']}\n"
                    if len(type_alerts) > 5:
                        summary += f"... et {len(type_alerts) - 5} autres"
                    
                    self.notifier.send_alert(summary)
            
        except Exception as e:
            logger.error(f"Erreur envoi alertes: {e}")
    
    def _generate_intelligence_report(self, sentiment: dict, trends: dict) -> str:
        """Génère le rapport d'intelligence de marché"""
        try:
            report = f"""🧠 **INTELLIGENCE DE MARCHÉ - {datetime.now().strftime('%d/%m/%Y %H:%M')}**

📊 **Sentiment Global:**
• Indice de peur/avidité: {sentiment.get('fear_greed_index', 'N/A')}
• Sentiment crypto: {sentiment.get('crypto_sentiment', 'N/A')}
• Volatilité: {sentiment.get('volatility', 'N/A')}

📈 **Tendances Détectées:**
"""
            
            for trend in trends.get('trends', [])[:5]:
                report += f"• {trend['description']}\n"
            
            report += f"""
💡 **Recommandations:**
• {sentiment.get('recommendation', 'Surveillance continue')}

🔍 *Analyse basée sur données temps réel*"""
            
            return report
            
        except Exception as e:
            logger.error(f"Erreur génération rapport: {e}")
            return "❌ Erreur génération rapport d'intelligence"

def main():
    """Fonction principale"""
    try:
        # Valider la configuration
        config.validate()
        
        # Créer le moniteur
        monitor = MarketMonitor()
        
        # Exécuter les analyses selon les arguments
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == 'crypto':
                monitor.run_crypto_surveillance()
            elif command == 'opportunities':
                monitor.run_opportunities_analysis()
            elif command == 'intelligence':
                monitor.run_market_intelligence()
            elif command == 'all':
                monitor.run_crypto_surveillance()
                monitor.run_opportunities_analysis()
                monitor.run_market_intelligence()
            else:
                print("Usage: python market_monitor.py [crypto|opportunities|intelligence|all]")
        else:
            # Par défaut, exécuter tout
            monitor.run_crypto_surveillance()
            monitor.run_opportunities_analysis()
            monitor.run_market_intelligence()
            
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 