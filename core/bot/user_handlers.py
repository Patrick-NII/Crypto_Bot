# core/bot/user_handlers.py
"""
Gestionnaires d'utilisateurs pour le bot Telegram GlueTrade
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from services.user_management.user_service import user_service
from core.database.models import User, Wallet

class UserHandlers:
    """Gestionnaires pour les interactions utilisateur"""
    
    def __init__(self):
        self.user_service = user_service
    
    def handle_start(self, update, context) -> str:
        """Gère la commande /start - Inscription et onboarding"""
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            
            # Enregistrer l'utilisateur
            registered_user = self.user_service.register_user(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name
            )
            
            if registered_user:
                # Générer le message d'onboarding
                welcome_message = self._generate_welcome_message(user, registered_user)
                
                # Créer les boutons d'action
                keyboard = [
                    [{"text": "📋 Remplir le profil", "callback_data": "fill_profile"}],
                    [{"text": "💎 Voir les abonnements", "callback_data": "subscriptions"}],
                    [{"text": "📊 Mon portfolio", "callback_data": "my_portfolio"}],
                    [{"text": "❓ Aide", "callback_data": "help"}]
                ]
                
                return {
                    'message': welcome_message,
                    'keyboard': keyboard,
                    'parse_mode': 'Markdown'
                }
            else:
                return {
                    'message': "❌ Erreur lors de l'inscription. Veuillez réessayer.",
                    'keyboard': None,
                    'parse_mode': 'Markdown'
                }
                
        except Exception as e:
            print(f"Erreur handle_start: {e}")
            return {
                'message': "❌ Erreur technique. Veuillez réessayer plus tard.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def handle_profile(self, update, context) -> str:
        """Gère la commande /profile - Affichage du profil"""
        try:
            user_id = update.effective_user.id
            
            # Récupérer le profil complet
            profile = self.user_service.get_user_profile(user_id)
            
            if profile:
                user = profile['user']
                wallets = profile['wallets']
                subscription = profile['subscription']
                
                # Générer le message de profil
                message = self._generate_profile_message(user, wallets, subscription)
                
                # Créer les boutons d'action
                keyboard = [
                    [{"text": "✏️ Modifier profil", "callback_data": "edit_profile"}],
                    [{"text": "💎 Upgrade abonnement", "callback_data": "upgrade"}],
                    [{"text": "📊 Gérer wallets", "callback_data": "manage_wallets"}],
                    [{"text": "🔙 Retour", "callback_data": "main_menu"}]
                ]
                
                return {
                    'message': message,
                    'keyboard': keyboard,
                    'parse_mode': 'Markdown'
                }
            else:
                return {
                    'message': "❌ Profil non trouvé. Utilisez /start pour vous inscrire.",
                    'keyboard': None,
                    'parse_mode': 'Markdown'
                }
                
        except Exception as e:
            print(f"Erreur handle_profile: {e}")
            return {
                'message': "❌ Erreur lors de la récupération du profil.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def handle_subscription(self, update, context) -> str:
        """Gère la commande /subscription - Informations abonnement"""
        try:
            user_id = update.effective_user.id
            
            # Récupérer les informations d'abonnement
            subscription_info = self.user_service.get_subscription_info(user_id)
            pricing = self.user_service.get_subscription_pricing()
            
            if subscription_info:
                message = self._generate_subscription_message(subscription_info, pricing)
                
                # Créer les boutons d'action
                keyboard = [
                    [{"text": "💎 Essentiel (19.99€)", "callback_data": "subscribe_basic"}],
                    [{"text": "🚀 Premium (49.99€)", "callback_data": "subscribe_premium"}],
                    [{"text": "👑 Pro (99.99€)", "callback_data": "subscribe_pro"}],
                    [{"text": "🔙 Retour", "callback_data": "main_menu"}]
                ]
                
                return {
                    'message': message,
                    'keyboard': keyboard,
                    'parse_mode': 'Markdown'
                }
            else:
                return {
                    'message': "❌ Informations d'abonnement non disponibles.",
                    'keyboard': None,
                    'parse_mode': 'Markdown'
                }
                
        except Exception as e:
            print(f"Erreur handle_subscription: {e}")
            return {
                'message': "❌ Erreur lors de la récupération des informations d'abonnement.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def handle_wallet(self, update, context) -> str:
        """Gère la commande /wallet - Gestion des wallets"""
        try:
            user_id = update.effective_user.id
            
            # Vérifier l'accès premium
            if not self.user_service.check_subscription_access(user_id, 'premium'):
                return {
                    'message': """🔒 **Fonctionnalité Premium Requise**

La gestion de wallet personnalisée nécessite un abonnement Premium.

💎 **Upgrade maintenant pour:**
• Suivi de vos portefeuilles en temps réel
• Alertes personnalisées
• Conseils IA adaptés
• Analyses quotidiennes

Utilisez /subscription pour voir les options disponibles.""",
                    'keyboard': [
                        [{"text": "💎 Voir abonnements", "callback_data": "subscriptions"}],
                        [{"text": "🔙 Retour", "callback_data": "main_menu"}]
                    ],
                    'parse_mode': 'Markdown'
                }
            
            # Récupérer les wallets
            wallets = self.user_service.get_wallet_summary(user_id)
            
            if wallets:
                message = self._generate_wallet_message(wallets)
                
                # Créer les boutons d'action
                keyboard = [
                    [{"text": "➕ Ajouter actif", "callback_data": "add_asset"}],
                    [{"text": "📊 Voir analyse", "callback_data": "wallet_analysis"}],
                    [{"text": "🚨 Gérer alertes", "callback_data": "manage_alerts"}],
                    [{"text": "🔙 Retour", "callback_data": "main_menu"}]
                ]
                
                return {
                    'message': message,
                    'keyboard': keyboard,
                    'parse_mode': 'Markdown'
                }
            else:
                return {
                    'message': """📊 **Aucun wallet configuré**

Pour commencer à suivre vos investissements:

1. Ajoutez vos premiers actifs
2. Configurez vos alertes
3. Recevez des conseils IA personnalisés

💡 **Conseil:** Commencez par ajouter vos cryptos principales (BTC, ETH)""",
                    'keyboard': [
                        [{"text": "➕ Ajouter actif", "callback_data": "add_asset"}],
                        [{"text": "🔙 Retour", "callback_data": "main_menu"}]
                    ],
                    'parse_mode': 'Markdown'
                }
                
        except Exception as e:
            print(f"Erreur handle_wallet: {e}")
            return {
                'message': "❌ Erreur lors de la gestion des wallets.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def handle_help(self, update, context) -> str:
        """Gère la commande /help - Aide et support"""
        try:
            message = """🤖 **GLUETRADE - AIDE ET SUPPORT**

📱 **Commandes principales:**
• `/start` - Inscription et onboarding
• `/profile` - Voir votre profil
• `/subscription` - Informations abonnement
• `/wallet` - Gérer vos portefeuilles (Premium)
• `/alerts` - Gérer vos alertes (Premium)
• `/advice` - Conseils IA (Premium)

📊 **Commandes analytiques:**
• `/ai` - Assistant IA avancé
• `/analyse` - Analyse technique
• `/opportunities` - Opportunités d'investissement
• `/sources` - Gestion sources RAG

💎 **Niveaux d'abonnement:**
• **Gratuit** - Canal + commandes de base
• **Essentiel** (19.99€) - Alertes + analyses
• **Premium** (49.99€) - Wallet + IA + alertes
• **Pro** (99.99€) - Tout + API + formation

📞 **Support:**
• Email: support@gluetrade.com
• Canal: @gluetrade_channel
• Groupe: @gluetrade_community

🔒 **Sécurité:**
• Vos données sont chiffrées
• Conformité RGPD
• Pas de partage de données personnelles

💡 **Conseil:** Remplissez votre profil pour des conseils IA plus pertinents !"""
            
            keyboard = [
                [{"text": "📋 Remplir profil", "callback_data": "fill_profile"}],
                [{"text": "💎 Voir abonnements", "callback_data": "subscriptions"}],
                [{"text": "🔙 Retour", "callback_data": "main_menu"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur handle_help: {e}")
            return {
                'message': "❌ Erreur lors de l'affichage de l'aide.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def _generate_welcome_message(self, telegram_user, registered_user) -> str:
        """Génère le message de bienvenue personnalisé"""
        try:
            subscription_info = self.user_service.get_subscription_info(telegram_user.id)
            
            message = f"""🎉 **BIENVENUE SUR GLUETRADE, {telegram_user.first_name or telegram_user.username or 'Investisseur'} !**

🤖 **Votre assistant IA crypto personnel**

📊 **Votre profil:**
• Niveau: {subscription_info['tier_name']}
• ID: {telegram_user.id}
• Inscrit le: {registered_user.created_at.strftime('%d/%m/%Y')}

💡 **Prochaines étapes recommandées:**
1. 📋 **Remplir votre profil** pour des conseils IA pertinents
2. 💎 **Découvrir les abonnements** Premium
3. 📊 **Configurer votre portfolio** (Premium)
4. 🚨 **Créer des alertes** personnalisées (Premium)

📢 **Canal de diffusion:** @gluetrade_channel
• Mises à jour marché toutes les 30 minutes
• Opportunités d'investissement
• Analyses techniques avancées

🔒 **Sécurité et confidentialité:**
• Vos données sont protégées
• Conformité RGPD
• Pas de partage de données personnelles

💎 **Upgrade Premium pour:**
• Suivi wallet personnalisé
• Alertes temps réel
• Conseils IA adaptés
• Analyses quotidiennes

Bienvenue dans la communauté GlueTrade ! 🚀"""
            
            return message
            
        except Exception as e:
            print(f"Erreur génération message bienvenue: {e}")
            return "Bienvenue sur GlueTrade ! Utilisez /help pour commencer."
    
    def _generate_profile_message(self, user, wallets, subscription) -> str:
        """Génère le message de profil"""
        try:
            # Calculer les totaux
            total_wallets = len(wallets)
            total_value = sum(w.total_value_usd for w in wallets)
            
            message = f"""👤 **PROFIL UTILISATEUR**

📋 **Informations personnelles:**
• Nom: {user.first_name or 'Non renseigné'}
• Username: @{user.username or 'Non renseigné'}
• ID Telegram: {user.telegram_id}
• Inscrit le: {user.created_at.strftime('%d/%m/%Y')}

🎯 **Profil d'investissement:**
• Niveau d'expérience: {user.experience_level.title()}
• Profil de risque: {user.risk_profile.title()}
• Objectifs: {', '.join(user.investment_goals) if user.investment_goals else 'Non renseignés'}

💎 **Abonnement:**
• Niveau: {user.subscription_tier.title()}
• Statut: {'✅ Actif' if subscription and subscription.is_active else '❌ Inactif'}
• Expire le: {user.subscription_expires.strftime('%d/%m/%Y') if user.subscription_expires else 'N/A'}

📊 **Portfolio:**
• Nombre de wallets: {total_wallets}
• Valeur totale: ${total_value:,.2f}
• Dernière mise à jour: {user.updated_at.strftime('%d/%m/%Y %H:%M')}

💡 **Recommandations:**
• Remplissez votre profil pour des conseils IA plus pertinents
• Configurez vos objectifs d'investissement
• Ajoutez vos actifs pour le suivi personnalisé"""
            
            return message
            
        except Exception as e:
            print(f"Erreur génération message profil: {e}")
            return "❌ Erreur lors de la génération du profil."
    
    def _generate_subscription_message(self, subscription_info, pricing) -> str:
        """Génère le message d'abonnement"""
        try:
            message = f"""💎 **ABONNEMENTS GLUETRADE**

📊 **Votre abonnement actuel:**
• Niveau: {subscription_info['tier_name']}
• Prix: {subscription_info['price']}€/mois
• Jours restants: {subscription_info['remaining_days']}
• Statut: {'✅ Actif' if subscription_info['is_active'] else '❌ Inactif'}

📋 **Niveaux disponibles:**

🆓 **GRATUIT**
• Prix: 0€
• Canal de diffusion
• Commandes de base
• Analyses générales

💎 **ESSENTIEL - 19.99€/mois**
• Canal de diffusion
• Alertes opportunités
• Analyses hebdomadaires
• Commandes avancées

🚀 **PREMIUM - 49.99€/mois**
• Tout Essentiel
• **Suivi wallet personnalisé**
• **Alertes temps réel**
• **Conseils IA personnalisés**
• **Analyses quotidiennes**

👑 **PRO - 99.99€/mois**
• Tout Premium
• **API accès**
• **Conseils avancés**
• **Formation et éducation**
• **Support prioritaire**

💳 **Méthodes de paiement:**
• Cryptomonnaies (BTC, ETH, USDT)
• Carte bancaire (bientôt disponible)
• PayPal (bientôt disponible)

🔒 **Garantie:**
• Essai gratuit 7 jours
• Remboursement 30 jours
• Annulation à tout moment"""
            
            return message
            
        except Exception as e:
            print(f"Erreur génération message abonnement: {e}")
            return "❌ Erreur lors de la génération des informations d'abonnement."
    
    def _generate_wallet_message(self, wallet_summary) -> str:
        """Génère le message de wallet"""
        try:
            message = f"""📊 **VOTRE PORTFOLIO**

💰 **Valeur totale:** ${wallet_summary['total_value_usd']:,.2f}
📈 **Nombre de wallets:** {wallet_summary['total_wallets']}
🎯 **Nombre d'actifs:** {len(wallet_summary['total_assets'])}

📋 **Top actifs:**
"""
            
            # Afficher les 5 premiers actifs par valeur
            sorted_assets = sorted(wallet_summary['total_assets'].items(), key=lambda x: x[1], reverse=True)
            
            for i, (crypto_id, amount) in enumerate(sorted_assets[:5], 1):
                message += f"{i}. {crypto_id.upper()}: {amount:,.4f}\n"
            
            message += f"""

💡 **Actions disponibles:**
• Ajouter de nouveaux actifs
• Voir l'analyse complète
• Configurer des alertes
• Recevoir des conseils IA

📅 **Dernière mise à jour:** {datetime.now().strftime('%d/%m/%Y %H:%M')}"""
            
            return message
            
        except Exception as e:
            print(f"Erreur génération message wallet: {e}")
            return "❌ Erreur lors de la génération du wallet."

# Instance globale
user_handlers = UserHandlers() 