# services/portfolio_management/wallet_monitor.py
"""
Système de surveillance personnalisée des wallets pour la plateforme Okamoey
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.database.manager import db_manager
from core.database.models import User, Wallet, Alert
from services.user_management.user_service import user_service

logger = logging.getLogger(__name__)

class WalletMonitor:
    """Moniteur de wallet personnalisé"""
    
    def __init__(self):
        self.db = db_manager
        self.user_service = user_service
        
    def get_crypto_price(self, crypto_id: str) -> Optional[float]:
        """Récupère le prix actuel d'une crypto"""
        try:
            import requests
            
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': crypto_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get(crypto_id, {}).get('usd')
            else:
                return None
                
        except Exception as e:
            logger.error(f"Erreur récupération prix {crypto_id}: {e}")
            return None
    
    def calculate_wallet_value(self, wallet: Wallet) -> float:
        """Calcule la valeur totale d'un wallet"""
        try:
            total_value = 0.0
            
            for crypto_id, amount in wallet.assets.items():
                price = self.get_crypto_price(crypto_id)
                if price:
                    total_value += amount * price
                    time.sleep(0.1)  # Pause pour éviter de surcharger l'API
            
            return total_value
            
        except Exception as e:
            logger.error(f"Erreur calcul valeur wallet: {e}")
            return wallet.total_value_usd
    
    def update_wallet_values(self, telegram_id: int) -> bool:
        """Met à jour les valeurs des wallets d'un utilisateur"""
        try:
            wallets = self.db.get_user_wallets(telegram_id)
            
            for wallet in wallets:
                new_value = self.calculate_wallet_value(wallet)
                wallet.total_value_usd = new_value
                wallet.updated_at = datetime.now()
                
                self.db.update_wallet(wallet)
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur mise à jour valeurs wallet: {e}")
            return False
    
    def check_alerts(self, telegram_id: int) -> List[Dict]:
        """Vérifie les alertes personnalisées d'un utilisateur"""
        try:
            alerts = self.db.get_user_alerts(telegram_id)
            triggered_alerts = []
            
            for alert in alerts:
                if not alert.is_active:
                    continue
                
                # Récupérer le prix actuel
                current_price = self.get_crypto_price(alert.crypto_id)
                if not current_price:
                    continue
                
                # Vérifier les conditions d'alerte
                triggered = False
                alert_message = ""
                
                if alert.alert_type == "price_above" and current_price > alert.threshold:
                    triggered = True
                    alert_message = f"🚀 {alert.crypto_id.upper()} a dépassé ${alert.threshold:,.2f} (Prix actuel: ${current_price:,.2f})"
                
                elif alert.alert_type == "price_below" and current_price < alert.threshold:
                    triggered = True
                    alert_message = f"📉 {alert.crypto_id.upper()} est tombé sous ${alert.threshold:,.2f} (Prix actuel: ${current_price:,.2f})"
                
                elif alert.alert_type == "price_change" and alert.threshold > 0:
                    # Calculer la variation depuis la dernière vérification
                    # Pour simplifier, on utilise un seuil fixe
                    if current_price > alert.threshold * 1.1:  # +10%
                        triggered = True
                        alert_message = f"📈 {alert.crypto_id.upper()} a augmenté de plus de 10%"
                
                if triggered:
                    alert.trigger()
                    self.db.update_alert(alert)
                    
                    triggered_alerts.append({
                        'alert': alert,
                        'message': alert_message,
                        'current_price': current_price
                    })
            
            return triggered_alerts
            
        except Exception as e:
            logger.error(f"Erreur vérification alertes: {e}")
            return []
    
    def generate_wallet_analysis(self, telegram_id: int) -> Optional[Dict]:
        """Génère une analyse complète du wallet d'un utilisateur"""
        try:
            # Récupérer les informations utilisateur
            user = self.db.get_user(telegram_id)
            if not user:
                return None
            
            # Mettre à jour les valeurs
            self.update_wallet_values(telegram_id)
            
            # Récupérer les wallets
            wallets = self.db.get_user_wallets(telegram_id)
            if not wallets:
                return None
            
            # Analyser chaque wallet
            wallet_analyses = []
            total_portfolio_value = 0
            
            for wallet in wallets:
                wallet_analysis = self._analyze_single_wallet(wallet, user)
                wallet_analyses.append(wallet_analysis)
                total_portfolio_value += wallet.total_value_usd
            
            # Analyse globale du portfolio
            portfolio_analysis = self._analyze_portfolio(wallets, user)
            
            return {
                'user': user,
                'total_portfolio_value': total_portfolio_value,
                'wallet_analyses': wallet_analyses,
                'portfolio_analysis': portfolio_analysis,
                'timestamp': datetime.now()
            }
            
        except Exception as e:
            logger.error(f"Erreur génération analyse wallet: {e}")
            return None
    
    def _analyze_single_wallet(self, wallet: Wallet, user: User) -> Dict:
        """Analyse un wallet individuel"""
        try:
            analysis = {
                'wallet_name': wallet.name,
                'total_value': wallet.total_value_usd,
                'asset_count': len(wallet.assets),
                'assets': [],
                'recommendations': []
            }
            
            # Analyser chaque actif
            for crypto_id, amount in wallet.assets.items():
                price = self.get_crypto_price(crypto_id)
                if price:
                    asset_value = amount * price
                    asset_percentage = (asset_value / wallet.total_value_usd * 100) if wallet.total_value_usd > 0 else 0
                    
                    asset_analysis = {
                        'crypto_id': crypto_id,
                        'amount': amount,
                        'price': price,
                        'value': asset_value,
                        'percentage': asset_percentage
                    }
                    
                    # Ajouter des recommandations basées sur le profil de risque
                    if user.risk_profile == "conservative" and asset_percentage > 20:
                        asset_analysis['recommendation'] = "Considérer la diversification"
                    elif user.risk_profile == "aggressive" and asset_percentage < 5:
                        asset_analysis['recommendation'] = "Potentiel d'augmentation"
                    
                    analysis['assets'].append(asset_analysis)
            
            # Recommandations générales pour le wallet
            if len(wallet.assets) < 3:
                analysis['recommendations'].append("Diversifiez votre portfolio avec plus d'actifs")
            
            if wallet.total_value_usd > 10000 and len(wallet.assets) < 5:
                analysis['recommendations'].append("Considérez ajouter des actifs de réserve")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Erreur analyse wallet individuel: {e}")
            return {}
    
    def _analyze_portfolio(self, wallets: List[Wallet], user: User) -> Dict:
        """Analyse globale du portfolio"""
        try:
            total_value = sum(w.total_value_usd for w in wallets)
            total_assets = {}
            
            # Compter les actifs totaux
            for wallet in wallets:
                for crypto_id, amount in wallet.assets.items():
                    if crypto_id not in total_assets:
                        total_assets[crypto_id] = 0
                    total_assets[crypto_id] += amount
            
            # Calculer la concentration
            concentration_score = len(total_assets) / max(len(wallets), 1)
            
            # Recommandations basées sur le profil
            recommendations = []
            
            if user.risk_profile == "conservative":
                if concentration_score < 0.5:
                    recommendations.append("Considérez réduire la concentration pour plus de sécurité")
                if len(total_assets) < 5:
                    recommendations.append("Ajoutez des actifs stables (BTC, ETH) pour la stabilité")
            
            elif user.risk_profile == "aggressive":
                if concentration_score > 2:
                    recommendations.append("Votre portfolio est bien diversifié pour la croissance")
                if len(total_assets) < 3:
                    recommendations.append("Ajoutez des actifs à fort potentiel pour maximiser les gains")
            
            else:  # moderate
                if concentration_score < 0.3:
                    recommendations.append("Considérez une diversification modérée")
                if len(total_assets) < 4:
                    recommendations.append("Ajoutez quelques actifs pour équilibrer votre portfolio")
            
            return {
                'total_value': total_value,
                'total_assets': total_assets,
                'asset_count': len(total_assets),
                'concentration_score': concentration_score,
                'recommendations': recommendations
            }
            
        except Exception as e:
            logger.error(f"Erreur analyse portfolio: {e}")
            return {}
    
    def generate_ai_advice(self, telegram_id: int) -> str:
        """Génère des conseils IA personnalisés"""
        try:
            # Vérifier l'accès premium
            if not self.user_service.check_subscription_access(telegram_id, 'premium'):
                return "🔒 Cette fonctionnalité nécessite un abonnement Premium. Utilisez /upgrade pour y accéder."
            
            # Générer l'analyse
            analysis = self.generate_wallet_analysis(telegram_id)
            if not analysis:
                return "❌ Impossible de générer l'analyse. Vérifiez que vous avez des actifs dans votre wallet."
            
            user = analysis['user']
            portfolio = analysis['portfolio_analysis']
            
            # Générer le message de conseils
            message = f"""🤖 **CONSEILS IA PERSONNALISÉS**

👤 **Profil:** {user.first_name or user.username}
📊 **Portfolio:** ${analysis['total_portfolio_value']:,.2f}
🎯 **Profil de risque:** {user.risk_profile.title()}

📈 **Analyse de votre portfolio:**
• Nombre d'actifs: {portfolio['asset_count']}
• Score de concentration: {portfolio['concentration_score']:.2f}
• Diversification: {'✅ Bonne' if portfolio['concentration_score'] > 0.5 else '⚠️ À améliorer'}

💡 **Recommandations:**
"""
            
            for rec in portfolio['recommendations'][:3]:
                message += f"• {rec}\n"
            
            # Conseils spécifiques par profil
            if user.risk_profile == "conservative":
                message += """
🔒 **Stratégie conservatrice:**
• Maintenez 60-70% en BTC/ETH
• 20-30% en stablecoins
• 10-20% en altcoins prometteurs
• Rééquilibrage mensuel recommandé"""
            
            elif user.risk_profile == "aggressive":
                message += """
🚀 **Stratégie agressive:**
• 40-50% en altcoins à fort potentiel
• 30-40% en BTC/ETH
• 10-20% en stablecoins
• Surveillance quotidienne recommandée"""
            
            else:
                message += """
⚖️ **Stratégie modérée:**
• 50-60% en BTC/ETH
• 20-30% en altcoins sélectionnés
• 10-20% en stablecoins
• Rééquilibrage bi-mensuel recommandé"""
            
            message += f"""

📅 **Prochaine analyse:** {datetime.now().strftime('%d/%m/%Y %H:%M')}
💎 *Conseils basés sur votre profil et les données de marché*"""
            
            return message
            
        except Exception as e:
            logger.error(f"Erreur génération conseils IA: {e}")
            return "❌ Erreur lors de la génération des conseils. Réessayez plus tard."
    
    def send_wallet_update(self, telegram_id: int) -> bool:
        """Envoie une mise à jour de wallet personnalisée"""
        try:
            # Vérifier l'accès premium
            if not self.user_service.check_subscription_access(telegram_id, 'premium'):
                return False
            
            # Générer l'analyse
            analysis = self.generate_wallet_analysis(telegram_id)
            if not analysis:
                return False
            
            # Vérifier les alertes
            triggered_alerts = self.check_alerts(telegram_id)
            
            # Générer le message
            message = self._format_wallet_update_message(analysis, triggered_alerts)
            
            # Envoyer via le service de notification
            from services.notification.telegram_notifier import telegram_notifier
            return telegram_notifier.send_alert(message, priority='normal')
            
        except Exception as e:
            logger.error(f"Erreur envoi mise à jour wallet: {e}")
            return False
    
    def _format_wallet_update_message(self, analysis: Dict, triggered_alerts: List[Dict]) -> str:
        """Formate le message de mise à jour wallet"""
        try:
            user = analysis['user']
            portfolio = analysis['portfolio_analysis']
            
            message = f"""📊 **MISE À JOUR WALLET - {user.first_name or user.username}**

💰 **Valeur totale:** ${analysis['total_portfolio_value']:,.2f}
📈 **Actifs:** {portfolio['asset_count']}
📅 **Date:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

🎯 **Top actifs:**
"""
            
            # Afficher les 3 premiers actifs par valeur
            all_assets = []
            for wallet_analysis in analysis['wallet_analyses']:
                for asset in wallet_analysis['assets']:
                    all_assets.append(asset)
            
            all_assets.sort(key=lambda x: x['value'], reverse=True)
            
            for i, asset in enumerate(all_assets[:3], 1):
                message += f"{i}. {asset['crypto_id'].upper()}: ${asset['value']:,.2f} ({asset['percentage']:.1f}%)\n"
            
            # Alertes déclenchées
            if triggered_alerts:
                message += "\n🚨 **Alertes déclenchées:**\n"
                for alert_info in triggered_alerts:
                    message += f"• {alert_info['message']}\n"
            
            # Recommandations principales
            if portfolio['recommendations']:
                message += f"\n💡 **Recommandation principale:**\n{portfolio['recommendations'][0]}"
            
            return message
            
        except Exception as e:
            logger.error(f"Erreur formatage message wallet: {e}")
            return "❌ Erreur formatage message wallet"

# Instance globale
wallet_monitor = WalletMonitor() 