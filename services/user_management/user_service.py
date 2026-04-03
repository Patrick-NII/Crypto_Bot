# services/user_management/user_service.py
"""
Service de gestion des utilisateurs pour la plateforme Okamoey
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from core.database.manager import db_manager
from core.database.models import User, Wallet, Subscription, Alert

class UserService:
    """Service de gestion des utilisateurs"""
    
    def __init__(self):
        self.db = db_manager
    
    def register_user(self, telegram_id: int, username: str = None, 
                     first_name: str = None, last_name: str = None) -> Optional[User]:
        """Enregistre un nouvel utilisateur"""
        try:
            # Vérifier si l'utilisateur existe déjà
            existing_user = self.db.get_user(telegram_id)
            if existing_user:
                return existing_user
            
            # Créer le nouvel utilisateur
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name
            )
            
            # Sauvegarder en base
            if self.db.create_user(user):
                # Créer un wallet par défaut
                default_wallet = Wallet(user_id=telegram_id, name="Portfolio Principal")
                self.db.create_wallet(default_wallet)
                
                return user
            else:
                return None
                
        except Exception as e:
            print(f"Erreur enregistrement utilisateur: {e}")
            return None
    
    def get_user_profile(self, telegram_id: int) -> Optional[Dict]:
        """Récupère le profil complet d'un utilisateur"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return None
            
            # Récupérer les wallets
            wallets = self.db.get_user_wallets(telegram_id)
            
            # Récupérer l'abonnement
            subscription = self.db.get_user_subscription(telegram_id)
            
            # Récupérer les alertes
            alerts = self.db.get_user_alerts(telegram_id)
            
            return {
                'user': user,
                'wallets': wallets,
                'subscription': subscription,
                'alerts': alerts
            }
            
        except Exception as e:
            print(f"Erreur récupération profil: {e}")
            return None
    
    def update_user_preferences(self, telegram_id: int, preferences: Dict) -> bool:
        """Met à jour les préférences d'un utilisateur"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return False
            
            user.preferences.update(preferences)
            user.updated_at = datetime.now()
            
            return self.db.update_user(user)
            
        except Exception as e:
            print(f"Erreur mise à jour préférences: {e}")
            return False
    
    def update_user_profile(self, telegram_id: int, **kwargs) -> bool:
        """Met à jour le profil utilisateur"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return False
            
            # Mettre à jour les champs fournis
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            
            user.updated_at = datetime.now()
            
            return self.db.update_user(user)
            
        except Exception as e:
            print(f"Erreur mise à jour profil: {e}")
            return False
    
    def create_subscription(self, telegram_id: int, tier: str, 
                          payment_method: str = "crypto") -> Optional[Subscription]:
        """Crée un abonnement pour un utilisateur"""
        try:
            # Vérifier que l'utilisateur existe
            user = self.db.get_user(telegram_id)
            if not user:
                return None
            
            # Créer l'abonnement
            subscription = Subscription(
                user_id=telegram_id,
                tier=tier,
                payment_method=payment_method
            )
            
            # Activer l'abonnement (30 jours par défaut)
            subscription.activate(duration_days=30)
            
            # Sauvegarder en base
            if self.db.create_subscription(subscription):
                # Mettre à jour le niveau d'abonnement de l'utilisateur
                self.db.update_user_subscription_tier(telegram_id, tier)
                return subscription
            else:
                return None
                
        except Exception as e:
            print(f"Erreur création abonnement: {e}")
            return None
    
    def get_subscription_info(self, telegram_id: int) -> Optional[Dict]:
        """Récupère les informations d'abonnement d'un utilisateur"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return None
            
            subscription = self.db.get_user_subscription(telegram_id)
            
            tier_info = Subscription.TIERS.get(user.subscription_tier, {})
            
            return {
                'tier': user.subscription_tier,
                'tier_name': tier_info.get('name', 'Inconnu'),
                'price': tier_info.get('price', 0),
                'features': tier_info.get('features', []),
                'expires_at': user.subscription_expires,
                'is_active': subscription.is_active if subscription else False,
                'remaining_days': subscription.get_remaining_days() if subscription else 0
            }
            
        except Exception as e:
            print(f"Erreur récupération abonnement: {e}")
            return None
    
    def check_subscription_access(self, telegram_id: int, required_tier: str) -> bool:
        """Vérifie si un utilisateur a accès à une fonctionnalité"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return False
            
            # Définir la hiérarchie des niveaux
            tier_hierarchy = {
                'free': 0,
                'basic': 1,
                'premium': 2,
                'pro': 3
            }
            
            user_tier_level = tier_hierarchy.get(user.subscription_tier, 0)
            required_tier_level = tier_hierarchy.get(required_tier, 0)
            
            # Vérifier si l'abonnement est actif
            subscription = self.db.get_user_subscription(telegram_id)
            if subscription and subscription.is_expired():
                return False
            
            return user_tier_level >= required_tier_level
            
        except Exception as e:
            print(f"Erreur vérification accès: {e}")
            return False
    
    def get_wallet_summary(self, telegram_id: int) -> Optional[Dict]:
        """Récupère un résumé du wallet d'un utilisateur"""
        try:
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
            
            return {
                'total_wallets': len(wallets),
                'total_value_usd': total_value,
                'total_assets': total_assets,
                'wallets': [w.to_dict() for w in wallets]
            }
            
        except Exception as e:
            print(f"Erreur résumé wallet: {e}")
            return None
    
    def create_alert(self, telegram_id: int, crypto_id: str, 
                    alert_type: str, threshold: float) -> Optional[Alert]:
        """Crée une alerte personnalisée"""
        try:
            # Vérifier que l'utilisateur a un abonnement premium
            if not self.check_subscription_access(telegram_id, 'premium'):
                return None
            
            alert = Alert(
                user_id=telegram_id,
                crypto_id=crypto_id,
                alert_type=alert_type,
                threshold=threshold
            )
            
            if self.db.create_alert(alert):
                return alert
            else:
                return None
                
        except Exception as e:
            print(f"Erreur création alerte: {e}")
            return None
    
    def get_user_alerts(self, telegram_id: int) -> List[Alert]:
        """Récupère toutes les alertes d'un utilisateur"""
        try:
            return self.db.get_user_alerts(telegram_id)
        except Exception as e:
            print(f"Erreur récupération alertes: {e}")
            return []
    
    def get_subscription_pricing(self) -> Dict:
        """Retourne les tarifs des abonnements"""
        return Subscription.TIERS
    
    def get_users_by_tier(self, tier: str) -> List[User]:
        """Récupère tous les utilisateurs d'un niveau d'abonnement"""
        try:
            return self.db.get_users_by_tier(tier)
        except Exception as e:
            print(f"Erreur récupération utilisateurs par tier: {e}")
            return []
    
    def get_expired_subscriptions(self) -> List[Subscription]:
        """Récupère tous les abonnements expirés"""
        try:
            return self.db.get_expired_subscriptions()
        except Exception as e:
            print(f"Erreur récupération abonnements expirés: {e}")
            return []
    
    def generate_onboarding_message(self, telegram_id: int) -> str:
        """Génère le message d'onboarding pour un nouvel utilisateur"""
        try:
            user = self.db.get_user(telegram_id)
            if not user:
                return "Erreur: Utilisateur non trouvé"
            
            subscription_info = self.get_subscription_info(telegram_id)
            
            message = f"""🎉 **Bienvenue sur Okamoey, {user.first_name or user.username or 'Investisseur'} !**

📊 **Votre profil:**
• Niveau d'abonnement: {subscription_info['tier_name']}
• Profil de risque: {user.risk_profile}
• Niveau d'expérience: {user.experience_level}

💡 **Commandes disponibles:**
• `/profile` - Voir votre profil
• `/wallet` - Gérer vos portefeuilles
• `/subscription` - Informations abonnement
• `/alerts` - Gérer vos alertes
• `/help` - Aide complète

🚀 **Prochaines étapes:**
1. Configurez votre profil de risque
2. Ajoutez vos premiers actifs
3. Créez des alertes personnalisées
4. Explorez les analyses avancées

💎 **Upgrade Premium:**
Accédez à des fonctionnalités exclusives avec `/upgrade`

Bienvenue dans la communauté Okamoey ! 🎯"""
            
            return message
            
        except Exception as e:
            print(f"Erreur génération message onboarding: {e}")
            return "Bienvenue sur Okamoey ! Utilisez /help pour commencer."

# Instance globale
user_service = UserService() 