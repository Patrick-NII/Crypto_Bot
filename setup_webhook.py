# setup_webhook.py
import requests
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TOKEN")

def setup_webhook():
    """Configure le webhook pour recevoir les messages"""
    
    # Option 1: Webhook avec ngrok (pour développement)
    # ngrok_url = "https://your-ngrok-url.ngrok.io/webhook"
    
    # Option 2: Polling (plus simple pour commencer)
    print("🔧 Configuration du bot pour recevoir les messages...")
    
    # D'abord, supprimer tout webhook existant
    delete_url = f"https://api.telegram.org/bot{TOKEN}/deleteWebhook"
    response = requests.post(delete_url)
    print(f"🗑️ Suppression webhook: {response.json()}")
    
    # Configurer pour recevoir les messages
    get_me_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
    response = requests.get(get_me_url)
    bot_info = response.json()
    
    if bot_info.get("ok"):
        bot_name = bot_info["result"]["first_name"]
        bot_username = bot_info["result"]["username"]
        print(f"✅ Bot configuré: {bot_name} (@{bot_username})")
        print(f"🔗 Lien direct: https://t.me/{bot_username}")
        print("\n📱 Maintenant vous pouvez:")
        print("1. Cliquer sur le lien ci-dessus")
        print("2. Commencer une conversation avec le bot")
        print("3. Envoyer /help pour tester")
    else:
        print(f"❌ Erreur: {bot_info}")

if __name__ == "__main__":
    setup_webhook() 