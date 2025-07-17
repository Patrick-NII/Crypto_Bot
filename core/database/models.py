# core/database/models.py
"""
Modèles de base de données pour la plateforme Okamoey
"""

from datetime import datetime, timedelta
from typing import Optional, List
import json

class User:
    """Modèle utilisateur"""
    
    def __init__(self, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
        self.telegram_id = telegram_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
        self.subscription_tier = "free"  # free, basic, premium, pro
        self.subscription_expires = None
        self.preferences = {}
        self.risk_profile = "moderate"  # conservative, moderate, aggressive
        self.investment_goals = []
        self.experience_level = "beginner"  # beginner, intermediate, advanced
        
    def to_dict(self):
        """Convertit en dictionnaire pour stockage"""
        return {
            'telegram_id': self.telegram_id,
            'username': self.username,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active,
            'subscription_tier': self.subscription_tier,
            'subscription_expires': self.subscription_expires.isoformat() if self.subscription_expires else None,
            'preferences': self.preferences,
            'risk_profile': self.risk_profile,
            'investment_goals': self.investment_goals,
            'experience_level': self.experience_level
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Crée un utilisateur depuis un dictionnaire"""
        user = cls(
            telegram_id=data['telegram_id'],
            username=data.get('username'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name')
        )
        user.created_at = datetime.fromisoformat(data['created_at'])
        user.updated_at = datetime.fromisoformat(data['updated_at'])
        user.is_active = data.get('is_active', True)
        user.subscription_tier = data.get('subscription_tier', 'free')
        user.subscription_expires = datetime.fromisoformat(data['subscription_expires']) if data.get('subscription_expires') else None
        user.preferences = data.get('preferences', {})
        user.risk_profile = data.get('risk_profile', 'moderate')
        user.investment_goals = data.get('investment_goals', [])
        user.experience_level = data.get('experience_level', 'beginner')
        return user

class Wallet:
    """Modèle wallet utilisateur"""
    
    def __init__(self, user_id: int, name: str = "Portfolio Principal"):
        self.id = None  # Sera défini par la DB
        self.user_id = user_id
        self.name = name
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
        self.total_value_usd = 0.0
        self.assets = {}  # {crypto_id: amount}
        self.target_allocation = {}  # {crypto_id: percentage}
        self.risk_level = "moderate"
        
    def add_asset(self, crypto_id: str, amount: float):
        """Ajoute un actif au wallet"""
        if crypto_id not in self.assets:
            self.assets[crypto_id] = 0.0
        self.assets[crypto_id] += amount
        self.updated_at = datetime.now()
    
    def remove_asset(self, crypto_id: str, amount: float):
        """Retire un actif du wallet"""
        if crypto_id in self.assets:
            self.assets[crypto_id] = max(0, self.assets[crypto_id] - amount)
            if self.assets[crypto_id] == 0:
                del self.assets[crypto_id]
        self.updated_at = datetime.now()
    
    def to_dict(self):
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active,
            'total_value_usd': self.total_value_usd,
            'assets': self.assets,
            'target_allocation': self.target_allocation,
            'risk_level': self.risk_level
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Crée un wallet depuis un dictionnaire"""
        wallet = cls(
            user_id=data['user_id'],
            name=data.get('name', 'Portfolio Principal')
        )
        wallet.id = data.get('id')
        wallet.created_at = datetime.fromisoformat(data['created_at'])
        wallet.updated_at = datetime.fromisoformat(data['updated_at'])
        wallet.is_active = data.get('is_active', True)
        wallet.total_value_usd = data.get('total_value_usd', 0.0)
        wallet.assets = data.get('assets', {})
        wallet.target_allocation = data.get('target_allocation', {})
        wallet.risk_level = data.get('risk_level', 'moderate')
        return wallet

class Subscription:
    """Modèle abonnement"""
    
    TIERS = {
        'free': {
            'name': 'Gratuit',
            'price': 0,
            'features': ['Accès au canal de diffusion', 'Commandes de base']
        },
        'basic': {
            'name': 'Essentiel',
            'price': 19.99,
            'features': ['Canal de diffusion', 'Alertes opportunités', 'Analyses hebdomadaires']
        },
        'premium': {
            'name': 'Premium',
            'price': 49.99,
            'features': ['Canal de diffusion', 'Suivi wallet personnalisé', 'Alertes temps réel', 'Conseils IA', 'Analyses quotidiennes']
        },
        'pro': {
            'name': 'Professionnel',
            'price': 99.99,
            'features': ['Tout Premium', 'API accès', 'Conseils personnalisés', 'Formation', 'Support prioritaire']
        }
    }
    
    def __init__(self, user_id: int, tier: str, payment_method: str = "crypto"):
        self.id = None
        self.user_id = user_id
        self.tier = tier
        self.payment_method = payment_method
        self.created_at = datetime.now()
        self.expires_at = None
        self.is_active = True
        self.payment_status = "pending"
        self.amount_paid = self.TIERS[tier]['price']
        
    def activate(self, duration_days: int = 30):
        """Active l'abonnement"""
        self.is_active = True
        self.payment_status = "paid"
        self.expires_at = datetime.now() + timedelta(days=duration_days)
        
    def is_expired(self) -> bool:
        """Vérifie si l'abonnement est expiré"""
        if not self.expires_at:
            return True
        return datetime.now() > self.expires_at
    
    def get_remaining_days(self) -> int:
        """Retourne le nombre de jours restants"""
        if not self.expires_at:
            return 0
        delta = self.expires_at - datetime.now()
        return max(0, delta.days)
    
    def to_dict(self):
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'tier': self.tier,
            'payment_method': self.payment_method,
            'created_at': self.created_at.isoformat(),
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'payment_status': self.payment_status,
            'amount_paid': self.amount_paid
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Crée un abonnement depuis un dictionnaire"""
        sub = cls(
            user_id=data['user_id'],
            tier=data['tier'],
            payment_method=data.get('payment_method', 'crypto')
        )
        sub.id = data.get('id')
        sub.created_at = datetime.fromisoformat(data['created_at'])
        sub.expires_at = datetime.fromisoformat(data['expires_at']) if data.get('expires_at') else None
        sub.is_active = data.get('is_active', True)
        sub.payment_status = data.get('payment_status', 'pending')
        sub.amount_paid = data.get('amount_paid', 0.0)
        return sub

class Alert:
    """Modèle alerte personnalisée"""
    
    def __init__(self, user_id: int, crypto_id: str, alert_type: str, threshold: float):
        self.id = None
        self.user_id = user_id
        self.crypto_id = crypto_id
        self.alert_type = alert_type  # price_above, price_below, volume_spike, etc.
        self.threshold = threshold
        self.created_at = datetime.now()
        self.is_active = True
        self.last_triggered = None
        self.trigger_count = 0
        
    def trigger(self):
        """Déclenche l'alerte"""
        self.last_triggered = datetime.now()
        self.trigger_count += 1
        
    def to_dict(self):
        """Convertit en dictionnaire"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'crypto_id': self.crypto_id,
            'alert_type': self.alert_type,
            'threshold': self.threshold,
            'created_at': self.created_at.isoformat(),
            'is_active': self.is_active,
            'last_triggered': self.last_triggered.isoformat() if self.last_triggered else None,
            'trigger_count': self.trigger_count
        }
    
    @classmethod
    def from_dict(cls, data: dict):
        """Crée une alerte depuis un dictionnaire"""
        alert = cls(
            user_id=data['user_id'],
            crypto_id=data['crypto_id'],
            alert_type=data['alert_type'],
            threshold=data['threshold']
        )
        alert.id = data.get('id')
        alert.created_at = datetime.fromisoformat(data['created_at'])
        alert.is_active = data.get('is_active', True)
        alert.last_triggered = datetime.fromisoformat(data['last_triggered']) if data.get('last_triggered') else None
        alert.trigger_count = data.get('trigger_count', 0)
        return alert 