# modules/chatbot_basic.py
import json
import random
from datetime import datetime

class BasicChatbot:
    def __init__(self):
        self.faq = {
            "qu'est-ce qu'un pea": {
                "question": "Qu'est-ce qu'un PEA ?",
                "answer": "Le **PEA (Plan d'Épargne en Actions)** est un compte français qui permet d'investir en actions européennes avec des avantages fiscaux après 5 ans de détention.\n\n💡 **Avantages :**\n• Exonération d'impôts après 5 ans\n• Frais réduits\n• Large choix d'actions européennes\n\n⚠️ **Limitations :**\n• Maximum 150 000€ de versements\n• Actions européennes uniquement\n• Blocage 5 ans minimum"
            },
            "qu'est-ce que la crypto": {
                "question": "Qu'est-ce que la cryptomonnaie ?",
                "answer": "Les **cryptomonnaies** sont des monnaies numériques décentralisées basées sur la blockchain.\n\n🔹 **Caractéristiques :**\n• Décentralisées (pas de banque centrale)\n• Sécurisées par cryptographie\n• Transparentes (blockchain publique)\n• Volatiles (prix très fluctuants)\n\n💡 **Exemples populaires :**\n• Bitcoin (BTC) - Réserve de valeur\n• Ethereum (ETH) - Plateforme smart contracts\n• Solana (SOL) - Transactions rapides"
            },
            "comment diversifier": {
                "question": "Comment diversifier mon portefeuille ?",
                "answer": "La **diversification** consiste à répartir vos investissements pour réduire les risques.\n\n📊 **Stratégies :**\n• **Par classe d'actifs** : Actions, obligations, crypto, immobilier\n• **Par secteur** : Tech, santé, énergie, finance\n• **Par géographie** : Europe, USA, Asie, émergents\n• **Par taille** : Grandes, moyennes, petites entreprises\n\n💡 **Règle d'or :** Ne mettez pas tous vos œufs dans le même panier !"
            },
            "qu'est-ce que la volatilité": {
                "question": "Qu'est-ce que la volatilité ?",
                "answer": "La **volatilité** mesure l'amplitude des variations de prix d'un actif.\n\n📈 **Volatilité élevée :**\n• Prix qui varient beaucoup\n• Risque plus élevé\n• Potentiel de gains/pertes importants\n• Exemple : Cryptomonnaies\n\n📉 **Volatilité faible :**\n• Prix relativement stables\n• Risque plus faible\n• Gains/pertes limités\n• Exemple : Obligations d'État"
            },
            "qu'est-ce que le dca": {
                "question": "Qu'est-ce que le DCA ?",
                "answer": "Le **DCA (Dollar Cost Averaging)** est une stratégie d'investissement régulier.\n\n💡 **Principe :**\n• Investir un montant fixe régulièrement\n• Peu importe le prix du moment\n• Lisse les variations de prix\n• Réduit le stress émotionnel\n\n📊 **Exemple :**\n• 100€ par mois en Bitcoin\n• Parfois à 40 000€, parfois à 60 000€\n• Prix moyen favorable sur le long terme\n\n✅ **Avantages :**\n• Automatise l'investissement\n• Évite le timing du marché\n• Discipline financière"
            }
        }
        
        self.lexicon = {
            "pump": "📈 **Pump** : Hausse rapide et importante du prix d'un actif, souvent due à un engouement soudain ou une manipulation.",
            "dump": "📉 **Dump** : Baisse rapide et importante du prix d'un actif, souvent due à des ventes massives.",
            "gap": "⚡ **Gap** : Écart entre le prix de clôture et le prix d'ouverture, créant un 'trou' dans le graphique.",
            "fomo": "😰 **FOMO (Fear Of Missing Out)** : Peur de rater une opportunité, poussant à acheter au plus haut.",
            "hodl": "💎 **HODL** : Terme crypto signifiant 'tenir' ses positions malgré les baisses (Hold On for Dear Life).",
            "bear market": "🐻 **Bear Market** : Marché baissier, période de déclin prolongé des prix.",
            "bull market": "🐮 **Bull Market** : Marché haussier, période de hausse prolongée des prix.",
            "market cap": "💰 **Market Cap** : Capitalisation boursière = Prix × Nombre d'actions/tokens en circulation.",
            "liquidity": "💧 **Liquidité** : Facilité à acheter/vendre un actif sans impacter son prix.",
            "whale": "🐋 **Whale** : Investisseur possédant de très gros montants, capable d'influencer les prix.",
            "altcoin": "🪙 **Altcoin** : Toute cryptomonnaie autre que Bitcoin.",
            "degen": "🎰 **Degen (Dégénéré)** : Investisseur prenant des risques extrêmes.",
            "rekt": "💥 **Rekt** : Terme crypto signifiant 'détruit', après de grosses pertes.",
            "moon": "🚀 **Moon** : Hausse spectaculaire du prix d'un actif.",
            "diamond hands": "💎 **Diamond Hands** : Investisseur qui tient ses positions malgré la volatilité."
        }
        
        self.descriptions = {
            "bot": "🤖 **Okamoey - Assistant Portfolio Intelligent**\n\nJe suis votre assistant personnel pour suivre et analyser vos investissements crypto et actions.\n\n📊 **Mes capacités :**\n• Analyse de portefeuille en temps réel\n• Surveillance des tendances\n• Conseils de diversification\n• Alertes personnalisées\n• Explications financières\n\n💡 **Comment m'utiliser :**\n• Commandes : `/help`, `/portfolio`, `/performance`\n• Questions : 'Qu'est-ce que le DCA ?'\n• Lexique : 'Définition pump'\n• Conversation : 'Comment ça va ?'",
            "alerts": "⚠️ **Système d'Alertes**\n\nJe surveille vos investissements 24h/24 :\n\n🚨 **Alertes automatiques :**\n• Variation > 5% sur portefeuille\n• Nouveaux sommets/creux\n• Volatilité anormale\n• Opportunités détectées\n\n⚙️ **Configuration :**\n• Seuils personnalisables\n• Fréquence d'alerte\n• Types d'actifs surveillés\n\n💡 Bientôt disponible : Alertes personnalisées !",
            "analysis": "📊 **Analyses Avancées**\n\nJe fournis des analyses détaillées :\n\n📈 **Performance :**\n• Comparaison avec indices\n• Analyse de la volatilité\n• Calcul des rendements\n\n🎯 **Risques :**\n• Score de diversification\n• Drawdown maximum\n• Corrélations entre actifs\n\n💡 **Tendances :**\n• Détection de patterns\n• Signaux techniques\n• Opportunités de marché"
        }
        
        self.greetings = [
            "👋 Bonjour ! Comment puis-je vous aider aujourd'hui ?",
            "🤖 Salut ! Je suis là pour analyser vos investissements.",
            "💼 Bonjour ! Prêt à optimiser votre portefeuille ?",
            "📊 Salut ! Besoin d'analyses sur vos investissements ?"
        ]
        
        self.farewells = [
            "😊 De rien ! N'hésitez pas si vous avez d'autres questions !",
            "🤖 Avec plaisir ! Je reste disponible pour vous aider.",
            "💡 Pas de souci ! Bon trading et à bientôt !",
            "📈 À votre service ! Bonne continuation !"
        ]

    def get_faq_answer(self, query):
        """Retourne une réponse FAQ"""
        query = query.lower().strip()
        
        for key, faq in self.faq.items():
            if key in query or any(word in query for word in faq["question"].lower().split()):
                return faq["answer"]
        
        return None

    def get_lexicon_definition(self, term):
        """Retourne la définition d'un terme"""
        term = term.lower().strip()
        
        for key, definition in self.lexicon.items():
            if key in term or term in key:
                return definition
        
        return None

    def get_description(self, topic):
        """Retourne une description détaillée"""
        topic = topic.lower().strip()
        
        for key, description in self.descriptions.items():
            if key in topic:
                return description
        
        return None

    def get_greeting(self):
        """Retourne une salutation aléatoire"""
        return random.choice(self.greetings)

    def get_farewell(self):
        """Retourne un message de fin aléatoire"""
        return random.choice(self.farewells)

    def process_basic_message(self, message):
        """Traite un message basique et retourne une réponse"""
        message = message.lower().strip()
        
        # FAQ
        if any(word in message for word in ["qu'est-ce que", "c'est quoi", "explique", "définition"]):
            faq_answer = self.get_faq_answer(message)
            if faq_answer:
                return faq_answer
        
        # Lexique
        if any(word in message for word in ["définition", "signifie", "terme", "lexique"]):
            for term in self.lexicon.keys():
                if term in message:
                    return self.lexicon[term]
        
        # Descriptions
        if any(word in message for word in ["description", "capacités", "fonctionnalités", "peux-tu faire"]):
            if "bot" in message or "assistant" in message:
                return self.descriptions["bot"]
            elif "alerte" in message:
                return self.descriptions["alerts"]
            elif "analyse" in message:
                return self.descriptions["analysis"]
        
        # Salutations
        if any(word in message for word in ["bonjour", "salut", "hello", "coucou"]):
            return self.get_greeting()
        
        # Remerciements
        if any(word in message for word in ["merci", "thanks", "thank you"]):
            return self.get_farewell()
        
        return None 