# core/database/manager.py
"""
Gestionnaire de base de données pour la plateforme GlueTrade
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from pathlib import Path

from .models import User, Wallet, Subscription, Alert

class DatabaseManager:
    """Gestionnaire de base de données"""
    
    def __init__(self, db_path: str = "data/gluetrade.db"):
        self.db_path = db_path
        self.ensure_db_directory()
        self.init_database()
    
    def ensure_db_directory(self):
        """Crée le répertoire de la base de données"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    def init_database(self):
        """Initialise la base de données avec les tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Table utilisateurs
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    subscription_tier TEXT DEFAULT 'free',
                    subscription_expires TEXT,
                    preferences TEXT,
                    risk_profile TEXT DEFAULT 'moderate',
                    investment_goals TEXT,
                    experience_level TEXT DEFAULT 'beginner'
                )
            ''')
            
            # Table wallets
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wallets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    total_value_usd REAL DEFAULT 0.0,
                    assets TEXT,
                    target_allocation TEXT,
                    risk_level TEXT DEFAULT 'moderate',
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Table abonnements
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    tier TEXT NOT NULL,
                    payment_method TEXT DEFAULT 'crypto',
                    created_at TEXT NOT NULL,
                    expires_at TEXT,
                    is_active BOOLEAN DEFAULT 1,
                    payment_status TEXT DEFAULT 'pending',
                    amount_paid REAL DEFAULT 0.0,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            # Table alertes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    crypto_id TEXT NOT NULL,
                    alert_type TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    last_triggered TEXT,
                    trigger_count INTEGER DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (telegram_id)
                )
            ''')
            
            conn.commit()
    
    # Gestion des utilisateurs
    def create_user(self, user: User) -> bool:
        """Crée un nouvel utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO users (
                        telegram_id, username, first_name, last_name, created_at, updated_at,
                        is_active, subscription_tier, subscription_expires, preferences,
                        risk_profile, investment_goals, experience_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user.telegram_id, user.username, user.first_name, user.last_name,
                    user.created_at.isoformat(), user.updated_at.isoformat(),
                    user.is_active, user.subscription_tier, 
                    user.subscription_expires.isoformat() if user.subscription_expires else None,
                    json.dumps(user.preferences), user.risk_profile,
                    json.dumps(user.investment_goals), user.experience_level
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur création utilisateur: {e}")
            return False
    
    def get_user(self, telegram_id: int) -> Optional[User]:
        """Récupère un utilisateur par son ID Telegram"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE telegram_id = ?', (telegram_id,))
                row = cursor.fetchone()
                
                if row:
                    return User.from_dict({
                        'telegram_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'created_at': row[4],
                        'updated_at': row[5],
                        'is_active': bool(row[6]),
                        'subscription_tier': row[7],
                        'subscription_expires': row[8],
                        'preferences': json.loads(row[9]) if row[9] else {},
                        'risk_profile': row[10],
                        'investment_goals': json.loads(row[11]) if row[11] else [],
                        'experience_level': row[12]
                    })
                return None
        except Exception as e:
            print(f"Erreur récupération utilisateur: {e}")
            return None
    
    def update_user(self, user: User) -> bool:
        """Met à jour un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET
                        username = ?, first_name = ?, last_name = ?, updated_at = ?,
                        is_active = ?, subscription_tier = ?, subscription_expires = ?,
                        preferences = ?, risk_profile = ?, investment_goals = ?, experience_level = ?
                    WHERE telegram_id = ?
                ''', (
                    user.username, user.first_name, user.last_name, user.updated_at.isoformat(),
                    user.is_active, user.subscription_tier,
                    user.subscription_expires.isoformat() if user.subscription_expires else None,
                    json.dumps(user.preferences), user.risk_profile,
                    json.dumps(user.investment_goals), user.experience_level, user.telegram_id
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur mise à jour utilisateur: {e}")
            return False
    
    def get_all_users(self) -> List[User]:
        """Récupère tous les utilisateurs"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE is_active = 1')
                rows = cursor.fetchall()
                
                users = []
                for row in rows:
                    users.append(User.from_dict({
                        'telegram_id': row[0],
                        'username': row[1],
                        'first_name': row[2],
                        'last_name': row[3],
                        'created_at': row[4],
                        'updated_at': row[5],
                        'is_active': bool(row[6]),
                        'subscription_tier': row[7],
                        'subscription_expires': row[8],
                        'preferences': json.loads(row[9]) if row[9] else {},
                        'risk_profile': row[10],
                        'investment_goals': json.loads(row[11]) if row[11] else [],
                        'experience_level': row[12]
                    }))
                return users
        except Exception as e:
            print(f"Erreur récupération utilisateurs: {e}")
            return []
    
    # Gestion des wallets
    def create_wallet(self, wallet: Wallet) -> bool:
        """Crée un nouveau wallet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO wallets (
                        user_id, name, created_at, updated_at, is_active,
                        total_value_usd, assets, target_allocation, risk_level
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    wallet.user_id, wallet.name, wallet.created_at.isoformat(),
                    wallet.updated_at.isoformat(), wallet.is_active,
                    wallet.total_value_usd, json.dumps(wallet.assets),
                    json.dumps(wallet.target_allocation), wallet.risk_level
                ))
                wallet.id = cursor.lastrowid
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur création wallet: {e}")
            return False
    
    def get_user_wallets(self, user_id: int) -> List[Wallet]:
        """Récupère tous les wallets d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM wallets WHERE user_id = ? AND is_active = 1', (user_id,))
                rows = cursor.fetchall()
                
                wallets = []
                for row in rows:
                    wallets.append(Wallet.from_dict({
                        'id': row[0],
                        'user_id': row[1],
                        'name': row[2],
                        'created_at': row[3],
                        'updated_at': row[4],
                        'is_active': bool(row[5]),
                        'total_value_usd': row[6],
                        'assets': json.loads(row[7]) if row[7] else {},
                        'target_allocation': json.loads(row[8]) if row[8] else {},
                        'risk_level': row[9]
                    }))
                return wallets
        except Exception as e:
            print(f"Erreur récupération wallets: {e}")
            return []
    
    def update_wallet(self, wallet: Wallet) -> bool:
        """Met à jour un wallet"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE wallets SET
                        name = ?, updated_at = ?, is_active = ?,
                        total_value_usd = ?, assets = ?, target_allocation = ?, risk_level = ?
                    WHERE id = ?
                ''', (
                    wallet.name, wallet.updated_at.isoformat(), wallet.is_active,
                    wallet.total_value_usd, json.dumps(wallet.assets),
                    json.dumps(wallet.target_allocation), wallet.risk_level, wallet.id
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur mise à jour wallet: {e}")
            return False
    
    # Gestion des abonnements
    def create_subscription(self, subscription: Subscription) -> bool:
        """Crée un nouvel abonnement"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO subscriptions (
                        user_id, tier, payment_method, created_at, expires_at,
                        is_active, payment_status, amount_paid
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    subscription.user_id, subscription.tier, subscription.payment_method,
                    subscription.created_at.isoformat(),
                    subscription.expires_at.isoformat() if subscription.expires_at else None,
                    subscription.is_active, subscription.payment_status, subscription.amount_paid
                ))
                subscription.id = cursor.lastrowid
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur création abonnement: {e}")
            return False
    
    def get_user_subscription(self, user_id: int) -> Optional[Subscription]:
        """Récupère l'abonnement actif d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM subscriptions 
                    WHERE user_id = ? AND is_active = 1 
                    ORDER BY created_at DESC LIMIT 1
                ''', (user_id,))
                row = cursor.fetchone()
                
                if row:
                    return Subscription.from_dict({
                        'id': row[0],
                        'user_id': row[1],
                        'tier': row[2],
                        'payment_method': row[3],
                        'created_at': row[4],
                        'expires_at': row[5],
                        'is_active': bool(row[6]),
                        'payment_status': row[7],
                        'amount_paid': row[8]
                    })
                return None
        except Exception as e:
            print(f"Erreur récupération abonnement: {e}")
            return None
    
    def update_user_subscription_tier(self, user_id: int, tier: str) -> bool:
        """Met à jour le niveau d'abonnement d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE users SET subscription_tier = ?, updated_at = ?
                    WHERE telegram_id = ?
                ''', (tier, datetime.now().isoformat(), user_id))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur mise à jour niveau abonnement: {e}")
            return False
    
    # Gestion des alertes
    def create_alert(self, alert: Alert) -> bool:
        """Crée une nouvelle alerte"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (
                        user_id, crypto_id, alert_type, threshold, created_at,
                        is_active, last_triggered, trigger_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert.user_id, alert.crypto_id, alert.alert_type, alert.threshold,
                    alert.created_at.isoformat(), alert.is_active,
                    alert.last_triggered.isoformat() if alert.last_triggered else None,
                    alert.trigger_count
                ))
                alert.id = cursor.lastrowid
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur création alerte: {e}")
            return False
    
    def get_user_alerts(self, user_id: int) -> List[Alert]:
        """Récupère toutes les alertes d'un utilisateur"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM alerts WHERE user_id = ? AND is_active = 1', (user_id,))
                rows = cursor.fetchall()
                
                alerts = []
                for row in rows:
                    alerts.append(Alert.from_dict({
                        'id': row[0],
                        'user_id': row[1],
                        'crypto_id': row[2],
                        'alert_type': row[3],
                        'threshold': row[4],
                        'created_at': row[5],
                        'is_active': bool(row[6]),
                        'last_triggered': row[7],
                        'trigger_count': row[8]
                    }))
                return alerts
        except Exception as e:
            print(f"Erreur récupération alertes: {e}")
            return []
    
    def update_alert(self, alert: Alert) -> bool:
        """Met à jour une alerte"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE alerts SET
                        is_active = ?, last_triggered = ?, trigger_count = ?
                    WHERE id = ?
                ''', (
                    alert.is_active,
                    alert.last_triggered.isoformat() if alert.last_triggered else None,
                    alert.trigger_count, alert.id
                ))
                conn.commit()
                return True
        except Exception as e:
            print(f"Erreur mise à jour alerte: {e}")
            return False
    
    # Utilitaires
    def get_users_by_tier(self, tier: str) -> List[User]:
        """Récupère tous les utilisateurs d'un niveau d'abonnement"""
        users = self.get_all_users()
        return [user for user in users if user.subscription_tier == tier]
    
    def get_expired_subscriptions(self) -> List[Subscription]:
        """Récupère tous les abonnements expirés"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM subscriptions 
                    WHERE expires_at < ? AND is_active = 1
                ''', (datetime.now().isoformat(),))
                rows = cursor.fetchall()
                
                subscriptions = []
                for row in rows:
                    subscriptions.append(Subscription.from_dict({
                        'id': row[0],
                        'user_id': row[1],
                        'tier': row[2],
                        'payment_method': row[3],
                        'created_at': row[4],
                        'expires_at': row[5],
                        'is_active': bool(row[6]),
                        'payment_status': row[7],
                        'amount_paid': row[8]
                    }))
                return subscriptions
        except Exception as e:
            print(f"Erreur récupération abonnements expirés: {e}")
            return []

# Instance globale
db_manager = DatabaseManager() 