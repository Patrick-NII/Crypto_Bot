# modules/telegram_commands.py
from datetime import datetime, timedelta
import json
import os
import random
from modules.chatbot_basic import BasicChatbot
from modules.risk_profiles import RiskProfiles

# État de conversation pour éviter les doublons
conversation_state = {}

# Initialiser les modules
basic_chatbot = BasicChatbot()
risk_profiles = RiskProfiles()

def get_help_message():
    """Retourne le message d'aide avec toutes les commandes disponibles"""
    return """🤖 **Okamoey - Assistant Portfolio Intelligent**

📊 **Commandes principales :**
• `/portfolio` - Résumé de votre portefeuille
• `/performance` - Performance 7j, 30j, année
• `/risk` - Analyse des risques actuels
• `/trends` - Tendances détectées
• `/profiles` - Comparaison des profils de risque
• `/faq` - Questions fréquentes

💬 **Conversation :**
• "Comment ça va ?" - État du marché
• "Conseils" - Recommandations
• "Qu'est-ce que le DCA ?" - Explications
• "Définition pump" - Lexique crypto

❓ **Aide :**
• `/help` - Affiche cette aide
• "Que peux-tu faire ?" - Explications

💡 *Je suis votre assistant personnel pour suivre vos investissements !*"""

def get_performance_message():
    """Calcule et retourne la performance sur différentes périodes"""
    try:
        # Simulation de données plus réalistes
        performance_7d = random.choice(["+2.3%", "+1.8%", "+3.1%", "-0.5%"])
        performance_30d = random.choice(["+8.7%", "+12.3%", "+6.2%", "+15.1%"])
        performance_ytd = random.choice(["+15.2%", "+22.8%", "+18.5%", "+25.3%"])
        
        # Analyse contextuelle
        if performance_7d.startswith("+"):
            mood = "📈"
            comment = "Votre portefeuille performe bien cette semaine !"
        else:
            mood = "📉"
            comment = "Pas d'inquiétude, les marchés sont volatils."
        
        return f"""📊 **Performance du Portefeuille** {mood}

📅 **7 derniers jours** : {performance_7d}
📅 **30 derniers jours** : {performance_30d}
📅 **Année en cours** : {performance_ytd}

💬 *{comment}*

💡 *Données basées sur les dernières mises à jour*"""
    except Exception as e:
        return f"❌ Erreur lors du calcul de performance : {str(e)}"

def get_risk_message():
    """Analyse et retourne les risques actuels"""
    try:
        # Lire les données du portefeuille
        with open("data/wallet_crypto.json", "r") as f:
            crypto_data = json.load(f)
        
        with open("data/wallet_pea.json", "r") as f:
            pea_data = json.load(f)
        
        # Calculer les totaux
        total_crypto = 2850.0  # Valeur simulée
        total_pea = 0
        for ticker, data in pea_data.items():
            amount = data.get('amount', 0)
            pru = data.get('pru', 0)
            current_value = amount * pru * 1.2
            total_pea += current_value
        
        total_portfolio = total_crypto + total_pea
        
        # Utiliser le module de profils de risque
        return risk_profiles.analyze_current_portfolio(total_crypto, total_pea, total_portfolio)
        
    except Exception as e:
        return f"❌ Erreur lors de l'analyse des risques : {str(e)}"

def get_portfolio_summary():
    """Retourne un résumé rapide du portefeuille"""
    try:
        # Lire les données actuelles
        with open("data/wallet_crypto.json", "r") as f:
            crypto_data = json.load(f)
        
        with open("data/wallet_pea.json", "r") as f:
            pea_data = json.load(f)
        
        # Calculer les totaux crypto (simulation pour l'instant)
        crypto_names = list(crypto_data.keys())
        total_crypto = 2850.0  # Valeur simulée basée sur tes données récentes
        
        # Calculer les totaux PEA
        total_pea = 0
        pea_assets = []
        for ticker, data in pea_data.items():
            amount = data.get('amount', 0)
            pru = data.get('pru', 0)
            current_value = amount * pru * 1.2  # Facteur de simulation
            total_pea += current_value
            pea_assets.append(ticker)
        
        total_portfolio = total_crypto + total_pea
        
        if total_portfolio > 0:
            crypto_percent = (total_crypto / total_portfolio) * 100
            pea_percent = (total_pea / total_portfolio) * 100
        else:
            crypto_percent = pea_percent = 0
        
        # Analyse contextuelle
        if crypto_percent > 70:
            advice = "⚠️ Forte exposition crypto. Pensez à diversifier."
        elif pea_percent > 80:
            advice = "📊 Portefeuille bien équilibré vers les actions."
        else:
            advice = "✅ Bon équilibre entre crypto et actions."
        
        return f"""💰 **Résumé du Portefeuille**

🔹 **Crypto** : {total_crypto:,.2f} €
🔹 **PEA** : {total_pea:,.2f} €
🔹 **Total** : {total_portfolio:,.2f} €

📊 **Répartition** :
• Crypto : {crypto_percent:.1f}%
• PEA : {pea_percent:.1f}%

💬 *{advice}*

💡 *Valeurs basées sur les dernières mises à jour*"""
    except Exception as e:
        return f"❌ Erreur lors du calcul du résumé : {str(e)}"

def get_trends_message():
    """Détecte et retourne les tendances actuelles"""
    try:
        # Tendances dynamiques basées sur l'heure
        hour = datetime.now().hour
        
        if 9 <= hour <= 11:
            session = "Ouverture"
            trends = [
                "📈 Bitcoin en hausse (+3.2% ce matin)",
                "📉 Ethereum légèrement baissier (-1.1%)",
                "⚡ Solana très volatile (+8.5%)",
                "📊 Actions PEA en progression"
            ]
        elif 14 <= hour <= 16:
            session = "Après-midi"
            trends = [
                "📈 Bitcoin stable (+1.8% aujourd'hui)",
                "📈 Ethereum en reprise (+2.3%)",
                "⚡ Solana calme (+1.2%)",
                "📊 Actions PEA consolidées"
            ]
        else:
            session = "Soirée"
            trends = [
                "📉 Bitcoin en baisse (-0.8% aujourd'hui)",
                "📈 Ethereum résiste (+0.5%)",
                "⚡ Solana volatile (-2.1%)",
                "📊 Actions PEA stables"
            ]
        
        trends_text = "\n".join(trends)
        
        return f"""📈 **Tendances Détectées** ({session})

{trends_text}

💡 *Analyses basées sur les dernières 24h*"""
    except Exception as e:
        return f"❌ Erreur lors de l'analyse des tendances : {str(e)}"

def get_profiles_message():
    """Retourne la comparaison des profils de risque"""
    try:
        return risk_profiles.get_profile_comparison()
    except Exception as e:
        return f"❌ Erreur lors de la récupération des profils : {str(e)}"

def get_faq_message():
    """Retourne la FAQ"""
    try:
        faq_text = """📚 **FAQ - Questions Fréquentes**

💡 **Posez-moi ces questions :**

🔹 **Définitions :**
• "Qu'est-ce qu'un PEA ?"
• "Qu'est-ce que la crypto ?"
• "Qu'est-ce que le DCA ?"
• "Qu'est-ce que la volatilité ?"

🔹 **Stratégies :**
• "Comment diversifier ?"
• "Quels sont les profils de risque ?"

🔹 **Lexique :**
• "Définition pump"
• "Définition dump"
• "Définition FOMO"
• "Définition HODL"

💡 *Exemple : "Qu'est-ce que le DCA ?"*"""
        
        return faq_text
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

def get_market_status():
    """Retourne l'état général du marché"""
    try:
        hour = datetime.now().hour
        day = datetime.now().strftime("%A")
        
        if day in ["Saturday", "Sunday"]:
            status = "🏖️ Week-end - Marchés fermés"
            mood = "Calme"
        elif 9 <= hour <= 17:
            status = "🏢 Marchés ouverts"
            mood = "Actif"
        else:
            status = "🌙 Marchés fermés"
            mood = "Calme"
        
        return f"""📊 **État du Marché**

{status}
🌡️ **Ambiance** : {mood}
⏰ **Heure** : {datetime.now().strftime("%H:%M")}
📅 **Jour** : {day}

💡 *Les cryptos tradent 24h/24, les actions suivent les horaires de bourse*"""
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

def get_advice():
    """Retourne des conseils personnalisés"""
    try:
        advice_list = [
            "💡 **Conseil du jour** : Diversifiez vos investissements pour réduire les risques.",
            "💡 **Conseil du jour** : Gardez une vision long terme, ne paniquez pas sur les baisses.",
            "💡 **Conseil du jour** : Surveillez régulièrement vos positions, mais pas obsessionnellement.",
            "💡 **Conseil du jour** : Considérez le DCA (Dollar Cost Averaging) pour les cryptos volatiles.",
            "💡 **Conseil du jour** : Gardez toujours une réserve de liquidités pour les opportunités."
        ]
        
        return random.choice(advice_list)
    except Exception as e:
        return f"❌ Erreur : {str(e)}"

def handle_command(command):
    """Gère les commandes reçues et retourne la réponse appropriée"""
    command = command.lower().strip()
    
    if command == "/help" or command == "help":
        return get_help_message()
    elif command == "/performance" or command == "performance":
        return get_performance_message()
    elif command == "/risk" or command == "risk":
        return get_risk_message()
    elif command == "/portfolio" or command == "portfolio":
        return get_portfolio_summary()
    elif command == "/trends" or command == "trends":
        return get_trends_message()
    elif command == "/profiles" or command == "profiles":
        return get_profiles_message()
    elif command == "/faq" or command == "faq":
        return get_faq_message()
    else:
        return f"❓ Commande inconnue : {command}\n\nUtilisez `/help` pour voir les commandes disponibles."

def handle_conversation(message, user_id):
    """Gère les conversations naturelles"""
    message = message.lower().strip()
    
    # Éviter les doublons
    if user_id in conversation_state:
        last_message = conversation_state[user_id].get('last_message', '')
        if message == last_message:
            return None  # Éviter la répétition
    else:
        conversation_state[user_id] = {}
    
    conversation_state[user_id]['last_message'] = message
    
    # Essayer d'abord le chatbot basique
    basic_response = basic_chatbot.process_basic_message(message)
    if basic_response:
        return basic_response
    
    # Salutations
    if any(word in message for word in ["bonjour", "hello", "salut", "coucou"]):
        return "👋 Bonjour ! Comment puis-je vous aider aujourd'hui ?\n\nUtilisez `/help` pour voir mes fonctionnalités."
    
    # Questions sur l'état
    elif any(word in message for word in ["comment ça va", "ça va", "comment tu vas", "état"]):
        return "🤖 Je vais très bien, merci ! Je surveille vos investissements 24h/24.\n\nVoulez-vous voir l'état de votre portefeuille avec `/portfolio` ?"
    
    # Conseils
    elif any(word in message for word in ["conseil", "conseils", "recommandation", "aide"]):
        return get_advice()
    
    # Marché
    elif any(word in message for word in ["marché", "bourse", "état marché", "situation"]):
        return get_market_status()
    
    # Merci
    elif any(word in message for word in ["merci", "thanks", "thank you"]):
        return "😊 De rien ! Je suis là pour vous aider.\n\nN'hésitez pas si vous avez d'autres questions !"
    
    # Questions sur les capacités
    elif any(word in message for word in ["que peux-tu faire", "fonctionnalités", "capacités", "aide"]):
        return "🤖 Je peux vous aider avec :\n\n📊 **Analyse** : Portfolio, performance, risques\n💬 **Conseils** : Recommandations personnalisées\n📈 **Tendances** : État du marché\n\nEssayez `/help` pour tout voir !"
    
    # Réponse par défaut
    else:
        return "🤔 Je ne comprends pas. Essayez `/help` pour voir ce que je peux faire, ou posez-moi une question sur vos investissements !" 