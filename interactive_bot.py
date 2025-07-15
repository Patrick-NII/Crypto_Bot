# interactive_bot.py
import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from modules.telegram_commands import handle_command, handle_conversation

load_dotenv()
TOKEN = os.getenv("TOKEN")

def send_message(text, chat_id):
    """Envoie un message Telegram"""
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=data)
        result = response.json()
        if result.get('ok'):
            print(f"✅ Message envoyé à {chat_id}")
        else:
            print(f"❌ Erreur envoi: {result}")
        return result
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return None

def get_updates(offset=None):
    """Récupère les nouveaux messages"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params)
        return response.json()
    except Exception as e:
        print(f"❌ Erreur récupération: {e}")
        return None

def process_message(message):
    """Traite un message reçu"""
    if "text" not in message:
        return
    
    text = message["text"]
    chat_id = message["chat"]["id"]
    user_id = message.get("from", {}).get("id", chat_id)
    user_name = message.get("from", {}).get("first_name", "Utilisateur")
    
    print(f"📨 {user_name}: {text}")
    
    # Traiter les commandes
    if text.startswith("/"):
        print(f"🔧 Commande détectée: {text}")
        response = handle_command(text)
        if response:
            send_message(response, chat_id)
    else:
        # Messages normaux - conversation naturelle
        print(f"💬 Message conversationnel: {text}")
        response = handle_conversation(text, user_id)
        
        # Ne pas envoyer de réponse si c'est un doublon
        if response:
            send_message(response, chat_id)
        else:
            print("🔄 Message ignoré (doublon)")

def run_interactive_bot():
    """Lance le bot interactif"""
    print("🤖 Bot interactif amélioré démarré...")
    print("📱 En attente de messages...")
    print("💡 Allez sur https://t.me/Okamoey_bot et testez :")
    print("   • /help - Commandes disponibles")
    print("   • 'Comment ça va ?' - Conversation naturelle")
    print("   • 'Conseils' - Recommandations")
    print("   • 'État du marché' - Informations marché")
    
    offset = None
    
    while True:
        try:
            updates = get_updates(offset)
            
            if updates and updates.get("ok"):
                for update in updates["result"]:
                    if "message" in update:
                        process_message(update["message"])
                        offset = update["update_id"] + 1
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\n🛑 Bot arrêté")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ TOKEN manquant")
        exit(1)
    
    print("🔗 Lien du bot: https://t.me/Okamoey_bot")
    print("📱 Commencez une conversation et testez les nouvelles fonctionnalités !")
    
    run_interactive_bot() 