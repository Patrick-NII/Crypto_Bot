# monitoring/cron_jobs/wallet_monitor_job.py
"""
Job de surveillance automatique des wallets pour la plateforme GlueTrade
"""

import os
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.database.manager import db_manager
from services.user_management.user_service import user_service
from services.portfolio_management.wallet_monitor import wallet_monitor

# Configuration de base
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/wallet_monitor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WalletMonitorJob:
    """Job de surveillance des wallets"""
    
    def __init__(self):
        self.db = db_manager
        self.user_service = user_service
        self.wallet_monitor = wallet_monitor
        
    def run_hourly_wallet_updates(self):
        """Exécute les mises à jour horaires des wallets"""
        try:
            logger.info("🔄 Démarrage surveillance wallets horaire...")
            
            # Récupérer tous les utilisateurs premium
            premium_users = self.user_service.get_users_by_tier('premium')
            pro_users = self.user_service.get_users_by_tier('pro')
            all_premium_users = premium_users + pro_users
            
            logger.info(f"📊 {len(all_premium_users)} utilisateurs premium détectés")
            
            success_count = 0
            error_count = 0
            
            for user in all_premium_users:
                try:
                    # Vérifier si l'utilisateur a des wallets
                    wallets = self.db.get_user_wallets(user.telegram_id)
                    if not wallets:
                        logger.info(f"⚠️ Utilisateur {user.telegram_id} n'a pas de wallets")
                        continue
                    
                    # Envoyer la mise à jour wallet
                    if self.wallet_monitor.send_wallet_update(user.telegram_id):
                        logger.info(f"✅ Mise à jour envoyée à {user.telegram_id}")
                        success_count += 1
                    else:
                        logger.warning(f"⚠️ Échec mise à jour pour {user.telegram_id}")
                        error_count += 1
                    
                    # Pause entre les utilisateurs
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur traitement utilisateur {user.telegram_id}: {e}")
                    error_count += 1
                    continue
            
            logger.info(f"✅ Surveillance wallets terminée - Succès: {success_count}, Erreurs: {error_count}")
            
        except Exception as e:
            logger.error(f"❌ Erreur surveillance wallets: {e}")
    
    def run_alert_check(self):
        """Vérifie et déclenche les alertes personnalisées"""
        try:
            logger.info("🚨 Démarrage vérification alertes...")
            
            # Récupérer tous les utilisateurs avec alertes
            all_users = self.user_service.get_all_users()
            
            triggered_count = 0
            
            for user in all_users:
                try:
                    # Vérifier les alertes de l'utilisateur
                    triggered_alerts = self.wallet_monitor.check_alerts(user.telegram_id)
                    
                    if triggered_alerts:
                        # Envoyer les alertes
                        for alert_info in triggered_alerts:
                            message = f"""🚨 **ALERTE PERSONNALISÉE**

{alert_info['message']}

💡 **Action recommandée:**
• Surveillez les mouvements de prix
• Considérez ajuster votre position
• Vérifiez les analyses techniques

📅 *{datetime.now().strftime('%d/%m/%Y %H:%M')}*"""
                            
                            # Envoyer l'alerte
                            from services.notification.telegram_notifier import telegram_notifier
                            telegram_notifier.send_alert(message, priority='high')
                            
                            triggered_count += 1
                            logger.info(f"🚨 Alerte déclenchée pour {user.telegram_id}: {alert_info['message']}")
                    
                    # Pause entre les utilisateurs
                    time.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur vérification alertes utilisateur {user.telegram_id}: {e}")
                    continue
            
            logger.info(f"✅ Vérification alertes terminée - {triggered_count} alertes déclenchées")
            
        except Exception as e:
            logger.error(f"❌ Erreur vérification alertes: {e}")
    
    def run_daily_portfolio_analysis(self):
        """Exécute l'analyse quotidienne des portfolios"""
        try:
            logger.info("📊 Démarrage analyse quotidienne portfolios...")
            
            # Récupérer tous les utilisateurs premium
            premium_users = self.user_service.get_users_by_tier('premium')
            pro_users = self.user_service.get_users_by_tier('pro')
            all_premium_users = premium_users + pro_users
            
            success_count = 0
            
            for user in all_premium_users:
                try:
                    # Générer l'analyse IA
                    ai_advice = self.wallet_monitor.generate_ai_advice(user.telegram_id)
                    
                    if ai_advice and not ai_advice.startswith("🔒"):
                        # Envoyer l'analyse
                        from services.notification.telegram_notifier import telegram_notifier
                        telegram_notifier.send_alert(ai_advice, priority='normal')
                        
                        success_count += 1
                        logger.info(f"✅ Analyse IA envoyée à {user.telegram_id}")
                    
                    # Pause entre les utilisateurs
                    time.sleep(3)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur analyse utilisateur {user.telegram_id}: {e}")
                    continue
            
            logger.info(f"✅ Analyse quotidienne terminée - {success_count} analyses envoyées")
            
        except Exception as e:
            logger.error(f"❌ Erreur analyse quotidienne: {e}")
    
    def run_subscription_cleanup(self):
        """Nettoie les abonnements expirés"""
        try:
            logger.info("🧹 Démarrage nettoyage abonnements...")
            
            # Récupérer les abonnements expirés
            expired_subscriptions = self.db.get_expired_subscriptions()
            
            cleaned_count = 0
            
            for subscription in expired_subscriptions:
                try:
                    # Mettre à jour le niveau d'abonnement
                    self.db.update_user_subscription_tier(subscription.user_id, 'free')
                    
                    # Désactiver l'abonnement
                    subscription.is_active = False
                    self.db.update_alert(subscription)
                    
                    # Envoyer notification d'expiration
                    message = f"""⚠️ **ABONNEMENT EXPIRÉ**

Votre abonnement {subscription.tier.title()} a expiré.

🔒 **Fonctionnalités restreintes:**
• Accès limité aux analyses avancées
• Alertes personnalisées désactivées
• Conseils IA non disponibles

💎 **Renouvelez votre abonnement:**
Utilisez /upgrade pour continuer à profiter de toutes les fonctionnalités.

📅 *{datetime.now().strftime('%d/%m/%Y %H:%M')}*"""
                    
                    from services.notification.telegram_notifier import telegram_notifier
                    telegram_notifier.send_alert(message, priority='medium')
                    
                    cleaned_count += 1
                    logger.info(f"🧹 Abonnement nettoyé pour {subscription.user_id}")
                    
                except Exception as e:
                    logger.error(f"❌ Erreur nettoyage abonnement {subscription.user_id}: {e}")
                    continue
            
            logger.info(f"✅ Nettoyage terminé - {cleaned_count} abonnements nettoyés")
            
        except Exception as e:
            logger.error(f"❌ Erreur nettoyage abonnements: {e}")
    
    def run_weekly_summary(self):
        """Génère un résumé hebdomadaire pour les utilisateurs premium"""
        try:
            logger.info("📈 Démarrage résumé hebdomadaire...")
            
            # Récupérer tous les utilisateurs premium
            premium_users = self.user_service.get_users_by_tier('premium')
            pro_users = self.user_service.get_users_by_tier('pro')
            all_premium_users = premium_users + pro_users
            
            success_count = 0
            
            for user in all_premium_users:
                try:
                    # Générer le résumé hebdomadaire
                    summary = self._generate_weekly_summary(user.telegram_id)
                    
                    if summary:
                        from services.notification.telegram_notifier import telegram_notifier
                        telegram_notifier.send_alert(summary, priority='normal')
                        
                        success_count += 1
                        logger.info(f"✅ Résumé hebdomadaire envoyé à {user.telegram_id}")
                    
                    # Pause entre les utilisateurs
                    time.sleep(2)
                    
                except Exception as e:
                    logger.error(f"❌ Erreur résumé utilisateur {user.telegram_id}: {e}")
                    continue
            
            logger.info(f"✅ Résumé hebdomadaire terminé - {success_count} résumés envoyés")
            
        except Exception as e:
            logger.error(f"❌ Erreur résumé hebdomadaire: {e}")
    
    def _generate_weekly_summary(self, telegram_id: int) -> str:
        """Génère un résumé hebdomadaire personnalisé"""
        try:
            # Récupérer les informations utilisateur
            user = self.db.get_user(telegram_id)
            if not user:
                return None
            
            # Récupérer les wallets
            wallets = self.db.get_user_wallets(telegram_id)
            if not wallets:
                return None
            
            # Calculer les totaux
            total_value = sum(w.total_value_usd for w in wallets)
            total_assets = {}
            
            for wallet in wallets:
                for crypto_id, amount in wallet.assets.items():
                    if crypto_id not in total_assets:
                        total_assets[crypto_id] = 0
                    total_assets[crypto_id] += amount
            
            # Générer le résumé
            message = f"""📊 **RÉSUMÉ HEBDOMADAIRE - {user.first_name or user.username}**

📅 **Période:** {datetime.now().strftime('%d/%m/%Y')}

💰 **Portfolio:**
• Valeur totale: ${total_value:,.2f}
• Nombre d'actifs: {len(total_assets)}
• Nombre de wallets: {len(wallets)}

🎯 **Top actifs:**
"""
            
            # Afficher les 3 premiers actifs
            sorted_assets = sorted(total_assets.items(), key=lambda x: x[1], reverse=True)
            for i, (crypto_id, amount) in enumerate(sorted_assets[:3], 1):
                message += f"{i}. {crypto_id.upper()}: {amount:,.4f}\n"
            
            # Conseils hebdomadaires
            if user.risk_profile == "conservative":
                message += """
💡 **Conseil de la semaine:**
Maintenez votre stratégie de diversification et surveillez les actifs stables."""
            elif user.risk_profile == "aggressive":
                message += """
💡 **Conseil de la semaine:**
Évaluez les opportunités de croissance et ajustez vos positions selon le marché."""
            else:
                message += """
💡 **Conseil de la semaine:**
Équilibrez votre portfolio et surveillez les tendances du marché."""
            
            message += f"""

📈 **Prochaine analyse:** {datetime.now().strftime('%d/%m/%Y')}
💎 *Résumé généré automatiquement*"""
            
            return message
            
        except Exception as e:
            logger.error(f"Erreur génération résumé hebdomadaire: {e}")
            return None

def main():
    """Fonction principale"""
    try:
        # Créer le répertoire logs
        Path("logs").mkdir(exist_ok=True)
        
        # Créer le job
        job = WalletMonitorJob()
        
        # Exécuter selon les arguments
        if len(sys.argv) > 1:
            command = sys.argv[1]
            
            if command == 'hourly':
                job.run_hourly_wallet_updates()
            elif command == 'alerts':
                job.run_alert_check()
            elif command == 'daily':
                job.run_daily_portfolio_analysis()
            elif command == 'cleanup':
                job.run_subscription_cleanup()
            elif command == 'weekly':
                job.run_weekly_summary()
            elif command == 'all':
                job.run_hourly_wallet_updates()
                time.sleep(5)
                job.run_alert_check()
                time.sleep(5)
                job.run_daily_portfolio_analysis()
            else:
                print("Usage: python wallet_monitor_job.py [hourly|alerts|daily|cleanup|weekly|all]")
        else:
            # Par défaut, exécuter la surveillance horaire
            job.run_hourly_wallet_updates()
            
    except Exception as e:
        logger.error(f"❌ Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 