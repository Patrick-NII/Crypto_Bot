#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de surveillance automatique pour Okamoey
Remplace les cron jobs en tournant en continu
"""

import os
import sys
import time
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

# Configuration de base
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/auto_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutoMonitor:
    """Moniteur automatique"""
    
    def __init__(self):
        self.running = False
        self.last_opportunities = None
        self.last_market_update = None
        self.last_intelligence = None
        
        # Intervalles en secondes
        self.opportunities_interval = 3600  # 1 heure
        self.market_interval = 1800         # 30 minutes
        self.intelligence_interval = 7200   # 2 heures
        
    def start(self):
        """Démarre le moniteur automatique"""
        logger.info("🚀 Démarrage du moniteur automatique Okamoey...")
        self.running = True
        
        # Démarrer les threads
        threads = [
            threading.Thread(target=self._opportunities_loop, daemon=True),
            threading.Thread(target=self._market_loop, daemon=True),
            threading.Thread(target=self._intelligence_loop, daemon=True)
        ]
        
        for thread in threads:
            thread.start()
        
        # Thread principal pour la gestion
        try:
            while self.running:
                time.sleep(60)  # Vérifier toutes les minutes
                
                # Log de statut toutes les heures
                if datetime.now().minute == 0:
                    logger.info("✅ Moniteur automatique actif")
                    
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt du moniteur automatique...")
            self.running = False
    
    def _opportunities_loop(self):
        """Boucle d'analyse des opportunités"""
        while self.running:
            try:
                logger.info("🔍 Lancement analyse opportunités...")
                
                # Importer et exécuter l'analyse
                from monitoring.cron_jobs.simple_monitor import analyze_crypto_opportunities
                analyze_crypto_opportunities()
                
                self.last_opportunities = datetime.now()
                logger.info(f"✅ Opportunités analysées à {self.last_opportunities.strftime('%H:%M')}")
                
            except Exception as e:
                logger.error(f"❌ Erreur analyse opportunités: {e}")
            
            # Attendre l'intervalle
            time.sleep(self.opportunities_interval)
    
    def _market_loop(self):
        """Boucle de mise à jour marché"""
        while self.running:
            try:
                logger.info("📊 Lancement mise à jour marché...")
                
                # Importer et exécuter la mise à jour
                from monitoring.cron_jobs.simple_monitor import send_market_update
                send_market_update()
                
                self.last_market_update = datetime.now()
                logger.info(f"✅ Marché mis à jour à {self.last_market_update.strftime('%H:%M')}")
                
            except Exception as e:
                logger.error(f"❌ Erreur mise à jour marché: {e}")
            
            # Attendre l'intervalle
            time.sleep(self.market_interval)
    
    def _intelligence_loop(self):
        """Boucle d'intelligence de marché"""
        while self.running:
            try:
                logger.info("🧠 Lancement intelligence de marché...")
                
                # Générer un rapport d'intelligence
                self._send_intelligence_report()
                
                self.last_intelligence = datetime.now()
                logger.info(f"✅ Intelligence générée à {self.last_intelligence.strftime('%H:%M')}")
                
            except Exception as e:
                logger.error(f"❌ Erreur intelligence: {e}")
            
            # Attendre l'intervalle
            time.sleep(self.intelligence_interval)
    
    def _send_intelligence_report(self):
        """Envoie un rapport d'intelligence"""
        try:
            from monitoring.cron_jobs.simple_monitor import send_telegram_message
            
            # Analyser quelques crypto pour le sentiment
            crypto_list = ["bitcoin", "ethereum", "binancecoin"]
            sentiment_data = []
            
            for crypto_id in crypto_list:
                try:
                    from monitoring.cron_jobs.simple_monitor import get_crypto_data
                    data = get_crypto_data(crypto_id)
                    if data:
                        market_data = data.get('market_data', {})
                        change_24h = market_data.get('price_change_percentage_24h', 0)
                        sentiment_data.append({
                            'name': data.get('name', crypto_id),
                            'change': change_24h
                        })
                except:
                    continue
            
            # Calculer le sentiment global
            if sentiment_data:
                avg_change = sum(d['change'] for d in sentiment_data) / len(sentiment_data)
                
                if avg_change > 5:
                    sentiment = "📈 Bullish"
                elif avg_change > 0:
                    sentiment = "📊 Neutre positif"
                elif avg_change > -5:
                    sentiment = "📊 Neutre négatif"
                else:
                    sentiment = "📉 Bearish"
                
                # Générer le rapport
                report = f"""🧠 **INTELLIGENCE DE MARCHÉ**

📅 **Date:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

📊 **Sentiment Global:** {sentiment}
📈 **Variation moyenne 24h:** {avg_change:+.2f}%

🎯 **Top Performers:**
"""
                
                # Trier par performance
                sentiment_data.sort(key=lambda x: x['change'], reverse=True)
                
                for i, crypto in enumerate(sentiment_data[:3], 1):
                    direction = "📈" if crypto['change'] > 0 else "📉"
                    report += f"{i}. {crypto['name']}: {direction} {crypto['change']:+.2f}%\n"
                
                report += f"""
💡 **Recommandations:**
• Surveillez les volumes
• Diversifiez votre portfolio
• Maintenez une stratégie de long terme

🔍 *Analyse basée sur données temps réel*"""
                
                send_telegram_message(report)
                
        except Exception as e:
            logger.error(f"Erreur rapport intelligence: {e}")
    
    def get_status(self):
        """Retourne le statut du moniteur"""
        return {
            'running': self.running,
            'last_opportunities': self.last_opportunities,
            'last_market_update': self.last_market_update,
            'last_intelligence': self.last_intelligence
        }

def main():
    """Fonction principale"""
    try:
        # Créer le répertoire logs
        Path("logs").mkdir(exist_ok=True)
        
        # Créer le moniteur
        monitor = AutoMonitor()
        
        # Démarrer le moniteur
        monitor.start()
        
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 