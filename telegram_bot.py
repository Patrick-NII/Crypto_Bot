# telegram_bot.py
import os
import requests
import time
from datetime import datetime
from dotenv import load_dotenv
from modules.telegram_commands import handle_command

load_dotenv()
TOKEN = os.getenv("TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

def send_message(text, chat_id=None):
    """Envoie un message Telegram"""
    if chat_id is None:
        chat_id = CHAT_ID
    
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, data=data)
        result = response.json()
        print(f"📤 Message envoyé: {result.get('ok', False)}")
        return result
    except Exception as e:
        print(f"❌ Erreur envoi message: {e}")
        return None

def get_updates(offset=None):
    """Récupère les nouveaux messages"""
    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    params = {"timeout": 30}
    if offset:
        params["offset"] = offset
    
    try:
        response = requests.get(url, params=params)
        result = response.json()
        if result.get("ok") and result.get("result"):
            print(f"📥 {len(result['result'])} nouveaux messages reçus")
        return result
    except Exception as e:
        print(f"❌ Erreur récupération updates: {e}")
        return None

def process_message(message):
    """Traite un message reçu"""
    if "text" not in message:
        print("⚠️ Message sans texte reçu")
        return
    
    text = message["text"]
    chat_id = message["chat"]["id"]
    user_name = message.get("from", {}).get("first_name", "Utilisateur")
    
    print(f"📨 Message reçu de {user_name} (ID: {chat_id}): '{text}'")
    
    # Vérifier si c'est une commande
    if text.startswith("/"):
        print(f"🔧 Commande détectée: {text}")
        try:
            response = handle_command(text)
            print(f"📤 Réponse à envoyer: {response[:100]}...")
            result = send_message(response, chat_id)
            if result and result.get("ok"):
                print("✅ Réponse envoyée avec succès")
            else:
                print(f"❌ Erreur envoi réponse: {result}")
        except Exception as e:
            print(f"❌ Erreur traitement commande: {e}")
            send_message(f"❌ Erreur lors du traitement de la commande: {str(e)}", chat_id)
    else:
        # Message normal - on peut ajouter des réponses automatiques
        print(f"💬 Message normal: {text}")
        if "bonjour" in text.lower() or "hello" in text.lower():
            send_message(f"Bonjour {user_name}! 👋\n\nUtilisez `/help` pour voir les commandes disponibles.", chat_id)
        elif "merci" in text.lower():
            send_message("De rien ! 😊", chat_id)
        else:
            send_message("Je ne comprends pas. Utilisez `/help` pour voir les commandes disponibles.", chat_id)

def run_bot():
    """Lance le bot en mode polling"""
    print("🤖 Bot Telegram démarré...")
    print("📱 En attente de messages...")
    print("💡 Envoyez /help pour voir les commandes")
    print(f"🔑 Token: {TOKEN[:10]}...")
    print(f"💬 Chat ID: {CHAT_ID}")
    
    offset = None
    
    while True:
        try:
            updates = get_updates(offset)
            
            if updates and updates.get("ok"):
                for update in updates["result"]:
                    if "message" in update:
                        process_message(update["message"])
                        offset = update["update_id"] + 1
                    else:
                        print(f"⚠️ Update sans message: {update}")
            elif updates:
                print(f"⚠️ Réponse API non OK: {updates}")
            
            time.sleep(2)  # Pause pour éviter de surcharger l'API
            
        except KeyboardInterrupt:
            print("\n🛑 Bot arrêté par l'utilisateur")
            break
        except Exception as e:
            print(f"❌ Erreur dans le bot: {e}")
            time.sleep(5)

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Erreur: TOKEN non trouvé dans le fichier .env")
        exit(1)
    
    if not CHAT_ID:
        print("❌ Erreur: CHAT_ID non trouvé dans le fichier .env")
        exit(1)
    
    # Test initial
    print("🧪 Test d'envoi de message...")
    test_response = send_message("🤖 Bot démarré avec succès!\n\nUtilisez `/help` pour voir les commandes.")
    
    if test_response and test_response.get("ok"):
        print("✅ Test réussi! Le bot peut envoyer des messages.")
        run_bot()
    else:
        print("❌ Erreur lors du test. Vérifiez votre TOKEN et CHAT_ID.")
        print(f"Réponse: {test_response}") 