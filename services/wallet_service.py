#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Service de gestion des wallets privés avec surveillance automatique
"""

import os
import json
import time
import asyncio
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional

class WalletService:
    def __init__(self):
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        self.users_file = self.data_dir / 'users.json'
        self.wallets_file = self.data_dir / 'user_wallets.json'
        self.monitoring_file = self.data_dir / 'monitoring.json'
        
        # Charger les données existantes
        self.load_data()
        
    def load_data(self):
        """Charge les données des utilisateurs et wallets"""
        # Charger les utilisateurs
        if self.users_file.exists():
            with open(self.users_file, 'r') as f:
                self.users = json.load(f)
        else:
            self.users = {}
            
        # Charger les wallets
        if self.wallets_file.exists():
            with open(self.wallets_file, 'r') as f:
                self.wallets = json.load(f)
        else:
            self.wallets = {}
            
        # Charger la surveillance
        if self.monitoring_file.exists():
            with open(self.monitoring_file, 'r') as f:
                self.monitoring = json.load(f)
        else:
            self.monitoring = {}
    
    def save_data(self):
        """Sauvegarde les données"""
        with open(self.users_file, 'w') as f:
            json.dump(self.users, f, indent=4)
        with open(self.wallets_file, 'w') as f:
            json.dump(self.wallets, f, indent=4)
        with open(self.monitoring_file, 'w') as f:
            json.dump(self.monitoring, f, indent=4)
    
    def add_user(self, chat_id: int, username: str, subscription: str = "max"):
        """Ajoute un utilisateur avec son abonnement"""
        self.users[str(chat_id)] = {
            "username": username,
            "subscription": subscription,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        self.save_data()
        print(f"✅ Utilisateur {username} (ID: {chat_id}) ajouté avec abonnement {subscription}")
    
    def set_user_wallet(self, chat_id: int, wallet_type: str, wallet_data: Dict):
        """Définit le wallet d'un utilisateur"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.wallets:
            self.wallets[chat_id_str] = {}
        
        self.wallets[chat_id_str][wallet_type] = wallet_data
        self.save_data()
        print(f"✅ Wallet {wallet_type} défini pour l'utilisateur {chat_id}")
    
    def get_user_wallet(self, chat_id: int) -> Dict:
        """Récupère le wallet d'un utilisateur"""
        chat_id_str = str(chat_id)
        return self.wallets.get(chat_id_str, {})
    
    def check_subscription(self, chat_id: int) -> Tuple[bool, str]:
        """Vérifie l'abonnement d'un utilisateur"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.users:
            return False, "Utilisateur non enregistré"
        
        subscription = self.users[chat_id_str]["subscription"]
        if subscription == "max":
            return True, "Abonnement maximum"
        elif subscription == "premium":
            return True, "Abonnement premium"
        elif subscription == "basic":
            return True, "Abonnement basique"
        else:
            return False, "Aucun abonnement"
    
    def generate_wallet_report(self, chat_id: int) -> str:
        """Génère un rapport de wallet privé"""
        chat_id_str = str(chat_id)
        if chat_id_str not in self.wallets:
            return "❌ Aucun wallet configuré pour cet utilisateur."
        
        user_info = self.users.get(chat_id_str, {})
        username = user_info.get("username", "Utilisateur")
        subscription = user_info.get("subscription", "inconnu")
        
        wallet_data = self.wallets[chat_id_str]
        
        # Générer le rapport
        report = f"""💰 **WALLET PRIVÉ - {username}**
📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}
💎 Abonnement: {subscription.upper()}

"""
        
        total_value = 0
        
        # Crypto
        if "crypto" in wallet_data:
            crypto_data = wallet_data["crypto"]
            report += "🔹 **CRYPTO (Revolut)**\n"
            crypto_total = 0
            
            for coin, amount in crypto_data.items():
                # Ici vous pouvez ajouter la logique pour récupérer les prix actuels
                # Pour l'instant, on utilise des valeurs estimées
                estimated_price = self.get_estimated_crypto_price(coin)
                value = amount * estimated_price
                crypto_total += value
                report += f"- {coin.title()}: {value:.2f} € ({amount} @ {estimated_price:.2f} €)\n"
            
            report += f"\n➡️ Total crypto: {crypto_total:.2f} €\n\n"
            total_value += crypto_total
        
        # PEA
        if "pea" in wallet_data:
            pea_data = wallet_data["pea"]
            report += "🔹 **PEA (Fortuneo)**\n"
            pea_total = 0
            
            for stock, info in pea_data.items():
                amount = info["amount"]
                pru = info["pru"]
                current_price = self.get_estimated_stock_price(stock)
                value = amount * current_price
                gain = value - (amount * pru)
                pea_total += value
                
                report += f"- {stock}: {value:.2f} € (PRU {pru:.2f} € / Gain: {gain:.2f} €)\n"
            
            report += f"\n➡️ Total PEA: {pea_total:.2f} €\n\n"
            total_value += pea_total
        
        # Actions
        if "stocks" in wallet_data:
            stocks_data = wallet_data["stocks"]
            report += "🔹 **ACTIONS (Revolut)**\n"
            stocks_total = 0
            
            for stock, info in stocks_data.items():
                amount = info["amount"]
                pru = info["pru"]
                current_price = self.get_estimated_stock_price(stock)
                value = amount * current_price
                gain = value - (amount * pru)
                stocks_total += value
                
                report += f"- {stock}: {value:.2f} € (PRU {pru:.2f} € / Gain: {gain:.2f} €)\n"
            
            report += f"\n➡️ Total actions: {stocks_total:.2f} €\n\n"
            total_value += stocks_total
        
        report += f"📊 **TOTAL PORTEFEUILLE: {total_value:.2f} €**\n\n"
        report += "🔄 Prochain rafraîchissement dans 3h"
        
        return report
    
    def get_estimated_crypto_price(self, coin: str) -> float:
        """Estime le prix d'une crypto (à remplacer par une vraie API)"""
        prices = {
            "bitcoin": 101000,
            "ethereum": 2700,
            "solana": 141,
            "render-token": 3.34,
            "fetch-ai": 0.64,
            "arbitrum": 0.38,
            "avalanche-2": 19.00
        }
        return prices.get(coin, 1.0)
    
    def get_estimated_stock_price(self, stock: str) -> float:
        """Estime le prix d'une action (à remplacer par une vraie API)"""
        prices = {
            "D7G.F": 0.23,
            "NAVYA.PA": 0.00,  # Délitée
            "ALEUP.PA": 0.005,
            "V07.F": 0.815,
            "XFAB.PA": 6.84
        }
        return prices.get(stock, 1.0)
    
    def start_monitoring(self, chat_id: int, interval_hours: int = 3):
        """Démarre la surveillance pour un utilisateur"""
        chat_id_str = str(chat_id)
        self.monitoring[chat_id_str] = {
            "active": True,
            "interval_hours": interval_hours,
            "last_check": datetime.now().isoformat(),
            "next_check": (datetime.now() + timedelta(hours=interval_hours)).isoformat()
        }
        self.save_data()
        print(f"✅ Surveillance démarrée pour l'utilisateur {chat_id} (intervalle: {interval_hours}h)")
    
    def stop_monitoring(self, chat_id: int):
        """Arrête la surveillance pour un utilisateur"""
        chat_id_str = str(chat_id)
        if chat_id_str in self.monitoring:
            self.monitoring[chat_id_str]["active"] = False
            self.save_data()
            print(f"✅ Surveillance arrêtée pour l'utilisateur {chat_id}")

# Instance globale
wallet_service = WalletService() 