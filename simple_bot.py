# simple_bot.py
import os
import requests
import time
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
        if not result.get('ok'):
            print(f"❌ Erreur API: {result}")
        return result
    except Exception as e:
        print(f"❌ Erreur envoi message: {e}")
        return None

def test_all_commands():
    """Teste toutes les commandes en les envoyant directement"""
    commands = [
        "/help",
        "/performance", 
        "/risk",
        "/portfolio",
        "/trends"
    ]
    
    print("🧪 Test de toutes les commandes...")
    
    for cmd in commands:
        print(f"\n📝 Test: {cmd}")
        try:
            response = handle_command(cmd)
            print(f"📤 Envoi de la réponse...")
            result = send_message(response)
            if result and result.get("ok"):
                print("✅ Commande envoyée avec succès")
            else:
                print(f"❌ Erreur: {result}")
        except Exception as e:
            print(f"❌ Erreur: {e}")
        
        time.sleep(1)  # Pause entre les messages
    
    print("\n✅ Tous les tests terminés!")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ Erreur: TOKEN non trouvé dans le fichier .env")
        exit(1)
    
    if not CHAT_ID:
        print("❌ Erreur: CHAT_ID non trouvé dans le fichier .env")
        exit(1)
    
    print("🤖 Bot de test démarré...")
    print(f"🔑 Token: {TOKEN[:10]}...")
    print(f"💬 Chat ID: {CHAT_ID}")
    
    # Test initial
    print("\n🧪 Test initial...")
    test_response = send_message("🤖 Bot de test démarré!\n\nJe vais tester toutes les commandes...")
    
    if test_response and test_response.get("ok"):
        print("✅ Test initial réussi!")
        test_all_commands()
    else:
        print("❌ Erreur lors du test initial.")
        print(f"Réponse: {test_response}") 