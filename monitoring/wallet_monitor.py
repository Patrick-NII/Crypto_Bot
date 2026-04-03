#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Système de surveillance automatique des wallets
Vérifie les fluctuations toutes les 3h et envoie des alertes
"""

import os
import sys
import time
import asyncio
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from services.wallet_service import wallet_service

class WalletMonitor:
    def __init__(self):
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        self.history_file = self.data_dir / 'wallet_history.json'
        self.fluctuation_threshold = 5.0  # 5% de fluctuation
        
        # Charger l'historique
        self.load_history()
        
    def load_history(self):
        """Charge l'historique des valeurs"""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = {}
    
    def save_history(self):
        """Sauvegarde l'historique"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=4)
    
    def get_current_wallet_value(self, chat_id: int) -> float:
        """Calcule la valeur actuelle du wallet"""
        wallet_data = wallet_service.get_user_wallet(chat_id)
        total_value = 0
        
        # Crypto
        if "crypto" in wallet_data:
            crypto_data = wallet_data["crypto"]
            for coin, amount in crypto_data.items():
                price = wallet_service.get_estimated_crypto_price(coin)
                total_value += amount * price
        
        # PEA
        if "pea" in wallet_data:
            pea_data = wallet_data["pea"]
            for stock, info in pea_data.items():
                price = wallet_service.get_estimated_stock_price(stock)
                total_value += info["amount"] * price
        
        # Actions
        if "stocks" in wallet_data:
            stocks_data = wallet_data["stocks"]
            for stock, info in stocks_data.items():
                price = wallet_service.get_estimated_stock_price(stock)
                total_value += info["amount"] * price
        
        return total_value
    
    def check_fluctuation(self, chat_id: int) -> Tuple[bool, float, float]:
        """Vérifie s'il y a une fluctuation significative"""
        chat_id_str = str(chat_id)
        current_value = self.get_current_wallet_value(chat_id)
        
        if chat_id_str not in self.history:
            # Première vérification
            self.history[chat_id_str] = {
                "last_value": current_value,
                "last_check": datetime.now().isoformat()
            }
            self.save_history()
            return False, current_value, 0.0
        
        last_value = self.history[chat_id_str]["last_value"]
        if last_value == 0:
            return False, current_value, 0.0
        
        # Calculer la fluctuation en pourcentage
        fluctuation_percent = ((current_value - last_value) / last_value) * 100
        
        # Mettre à jour l'historique
        self.history[chat_id_str] = {
            "last_value": current_value,
            "last_check": datetime.now().isoformat()
        }
        self.save_history()
        
        # Vérifier si la fluctuation dépasse le seuil
        significant_fluctuation = abs(fluctuation_percent) >= self.fluctuation_threshold
        
        return significant_fluctuation, current_value, fluctuation_percent
    
    def send_alert(self, chat_id: int, fluctuation_percent: float, current_value: float):
        """Envoie une alerte à l'utilisateur"""
        try:
            # Charger les variables d'environnement
            from dotenv import load_dotenv
            load_dotenv()
            
            token = os.getenv('TOKEN')
            if not token:
                print("❌ Token Telegram non trouvé")
                return
            
            # Préparer le message
            direction = "📈" if fluctuation_percent > 0 else "📉"
            message = f"""🚨 **ALERTE FLUCTUATION DÉTECTÉE**

{direction} Votre portefeuille a connu une fluctuation de **{fluctuation_percent:.2f}%**

💰 **Valeur actuelle:** {current_value:.2f} €

📊 **Détails:**
• Seuil d'alerte: {self.fluctuation_threshold}%
• Fluctuation: {fluctuation_percent:.2f}%
• Heure: {datetime.now().strftime('%d/%m/%Y %H:%M')}

💡 **Conseil:** Utilisez `/wallet` pour voir le détail complet de votre portefeuille.

🔄 Prochaine vérification dans 3h"""
            
            # Envoyer le message
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"✅ Alerte envoyée à l'utilisateur {chat_id}")
                else:
                    print(f"❌ Erreur envoi alerte: {result}")
            else:
                print(f"❌ Erreur HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi de l'alerte: {e}")
    
    def send_regular_update(self, chat_id: int):
        """Envoie une mise à jour régulière (toutes les 3h)"""
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            token = os.getenv('TOKEN')
            if not token:
                print("❌ Token Telegram non trouvé")
                return
            
            # Générer le rapport
            report = wallet_service.generate_wallet_report(chat_id)
            
            # Envoyer le message
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": report,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, data=data)
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    print(f"✅ Mise à jour envoyée à l'utilisateur {chat_id}")
                else:
                    print(f"❌ Erreur envoi mise à jour: {result}")
            else:
                print(f"❌ Erreur HTTP: {response.status_code}")
                
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi de la mise à jour: {e}")
    
    def check_all_users(self):
        """Vérifie tous les utilisateurs surveillés"""
        print(f"🔄 Vérification des wallets - {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        
        for chat_id_str, monitoring_info in wallet_service.monitoring.items():
            if not monitoring_info.get("active", False):
                continue
            
            chat_id = int(chat_id_str)
            
            # Vérifier l'abonnement
            has_access, _ = wallet_service.check_subscription(chat_id)
            if not has_access:
                continue
            
            # Vérifier la fluctuation
            significant_fluctuation, current_value, fluctuation_percent = self.check_fluctuation(chat_id)
            
            if significant_fluctuation:
                print(f"🚨 Fluctuation détectée pour {chat_id}: {fluctuation_percent:.2f}%")
                self.send_alert(chat_id, fluctuation_percent, current_value)
            else:
                print(f"✅ Pas de fluctuation significative pour {chat_id}")
                # Envoyer une mise à jour régulière
                self.send_regular_update(chat_id)
    
    def run_monitoring_loop(self, interval_hours: int = 3):
        """Boucle principale de surveillance"""
        print(f"🚀 Démarrage de la surveillance des wallets (intervalle: {interval_hours}h)")
        
        while True:
            try:
                self.check_all_users()
                print(f"⏰ Prochaine vérification dans {interval_hours} heures...")
                time.sleep(interval_hours * 3600)  # Attendre interval_hours heures
                
            except KeyboardInterrupt:
                print("\n🛑 Surveillance arrêtée par l'utilisateur")
                break
            except Exception as e:
                print(f"❌ Erreur dans la boucle de surveillance: {e}")
                time.sleep(300)  # Attendre 5 minutes en cas d'erreur

# Instance globale
wallet_monitor = WalletMonitor()

if __name__ == "__main__":
    # Test rapide
    print("🧪 Test du système de surveillance")
    wallet_monitor.check_all_users() 