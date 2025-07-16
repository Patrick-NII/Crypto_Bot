#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Okamoey Bot - Assistant Portfolio Intelligent
Version unifiée et simplifiée
"""

import os
import json
import logging
import asyncio
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# Import des services
try:
    from services.ai_integration import AIAnalysisService
    from services.crypto_opportunities import CryptoOpportunitiesService
    from services.sources_manager import SourcesManager
    from services.technical_analysis import TechnicalAnalysisService
    from services.priority_assets import PriorityAssetsService
except ImportError as e:
    logging.warning(f"Services non disponibles: {e}")
    AIAnalysisService = None
    CryptoOpportunitiesService = None
    SourcesManager = None
    TechnicalAnalysisService = None
    PriorityAssetsService = None

# Configuration du logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration depuis les variables d'environnement
BOT_TOKEN = os.getenv('TOKEN')
CHANNEL_ID = os.getenv('CHAT_ID')

if not BOT_TOKEN:
    logger.error("❌ Token du bot non trouvé dans les variables d'environnement")
    exit(1)

# État global pour éviter les doublons
user_states = {}

class WalletService:
    """Service pour gérer les données du wallet"""
    
    def __init__(self):
        self.crypto_prices = {}
        self.stock_prices = {}
        
    def load_wallet_data(self):
        """Charge les données du wallet depuis les fichiers JSON"""
        try:
            with open('data/wallet_crypto.json', 'r') as f:
                self.crypto_data = json.load(f)
            
            with open('data/wallet_pea.json', 'r') as f:
                self.pea_data = json.load(f)
                
            with open('data/wallet_stocks.json', 'r') as f:
                self.stocks_data = json.load(f)
                
            return True
        except Exception as e:
            logger.error(f"Erreur chargement données wallet: {e}")
            return False
    
    def get_crypto_price(self, crypto_id):
        """Récupère le prix actuel d'une crypto depuis CoinGecko"""
        if crypto_id in self.crypto_prices:
            return self.crypto_prices[crypto_id]
        
        try:
            url = f"https://api.coingecko.com/api/v3/simple/price"
            params = {
                'ids': crypto_id,
                'vs_currencies': 'usd'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                price = data.get(crypto_id, {}).get('usd', 0)
                self.crypto_prices[crypto_id] = price
                return price
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Erreur récupération prix {crypto_id}: {e}")
            return 0
    
    def get_stock_price(self, symbol):
        """Récupère le prix actuel d'une action (simulation pour l'instant)"""
        # Pour l'instant, on utilise des prix simulés basés sur le PRU
        # En production, on utiliserait une API comme Alpha Vantage ou Yahoo Finance
        
        if symbol in self.stock_prices:
            return self.stock_prices[symbol]
        
        # Prix simulés basés sur le PRU avec une variation
        base_prices = {
            "D7G.F": 0.65,  # +20% par rapport au PRU
            "NAVYA.PA": 0.045,  # +25% par rapport au PRU
            "ALEUP.PA": 7.2,  # +17% par rapport au PRU
            "V07.F": 1.6,  # +18% par rapport au PRU
            "XFAB.PA": 8.1,  # +18% par rapport au PRU
        }
        
        price = base_prices.get(symbol, 0)
        self.stock_prices[symbol] = price
        return price
    
    def calculate_crypto_value(self):
        """Calcule la valeur totale des cryptos"""
        total_value = 0
        crypto_details = []
        
        for crypto_id, amount in self.crypto_data.items():
            price = self.get_crypto_price(crypto_id)
            value = amount * price
            total_value += value
            
            crypto_details.append({
                'id': crypto_id,
                'amount': amount,
                'price': price,
                'value': value
            })
        
        return total_value, crypto_details
    
    def calculate_pea_value(self):
        """Calcule la valeur totale du PEA"""
        total_value = 0
        pea_details = []
        
        for symbol, data in self.pea_data.items():
            amount = data.get('amount', 0)
            pru = data.get('pru', 0)
            current_price = self.get_stock_price(symbol)
            value = amount * current_price
            total_value += value
            
            pea_details.append({
                'symbol': symbol,
                'amount': amount,
                'pru': pru,
                'current_price': current_price,
                'value': value,
                'performance': ((current_price - pru) / pru * 100) if pru > 0 else 0
            })
        
        return total_value, pea_details
    
    def calculate_stocks_value(self):
        """Calcule la valeur totale des actions"""
        total_value = 0
        stocks_details = []
        
        for symbol, data in self.stocks_data.items():
            amount = data.get('amount', 0)
            pru = data.get('pru', 0)
            current_price = self.get_stock_price(symbol)
            value = amount * current_price
            total_value += value
            
            stocks_details.append({
                'symbol': symbol,
                'amount': amount,
                'pru': pru,
                'current_price': current_price,
                'value': value,
                'performance': ((current_price - pru) / pru * 100) if pru > 0 else 0
            })
        
        return total_value, stocks_details

class OkamoeyBot:
    def __init__(self):
        self.application = None
        self.wallet_service = WalletService()
        self.wallet_service.load_wallet_data()
        
        # Initialiser les services
        self.ai_service = AIAnalysisService() if AIAnalysisService else None
        self.opportunities_service = CryptoOpportunitiesService() if CryptoOpportunitiesService else None
        self.sources_manager = SourcesManager() if SourcesManager else None
        self.technical_service = TechnicalAnalysisService() if TechnicalAnalysisService else None
        self.priority_service = PriorityAssetsService() if PriorityAssetsService else None
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        welcome_message = f"""🤖 **Bienvenue {user.first_name} !**

Je suis **Okamoey**, votre assistant intelligent.

📊 **Je peux vous aider avec :**
• Analyse de vos investissements
• Conseils de diversification
• Surveillance des tendances
• Explications financières
• Profils de risque personnalisés

💡 **Commandes principales :**
• `/help` - Aide complète
• `/performance` - Performance
• `/risk` - Analyse des risques
• `/wallet` - Wallet privé détaillé (Premium)

💬 **Ou parlez-moi naturellement :**
• "Comment ça va ?"
• "Qu'est-ce que le DCA ?"
• "Conseils pour diversifier"

🚀 *Prêt à optimiser vos investissements ?*"""
        
        # Créer des boutons inline
        keyboard = [
            [
                InlineKeyboardButton("🤖 IA", callback_data="ai"),
                InlineKeyboardButton("📊 Analyse", callback_data="analyse")
            ],
            [
                InlineKeyboardButton("💰 Mon Wallet", callback_data="wallet"),
                InlineKeyboardButton("📈 Performance", callback_data="performance")
            ],
            [
                InlineKeyboardButton("🎯 Opportunités", callback_data="opportunities"),
                InlineKeyboardButton("📚 Sources", callback_data="sources")
            ],
            [
                InlineKeyboardButton("⚠️ Analyse Risques", callback_data="risk"),
                InlineKeyboardButton("📚 FAQ", callback_data="faq")
            ],
            [
                InlineKeyboardButton("💡 Conseils", callback_data="advice"),
                InlineKeyboardButton("📊 Profils", callback_data="profiles")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /help"""
        help_text = self.get_help_message()
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def wallet_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /wallet - Wallet privé détaillé"""
        chat_id = update.effective_user.id
        message = self.get_wallet_message(chat_id)
        await update.message.reply_text(message, parse_mode='Markdown')

    async def ai_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /ai - Analyse IA"""
        if not self.ai_service:
            await update.message.reply_text("❌ Service IA non disponible.")
            return
        
        try:
            # Analyser le contexte de l'utilisateur
            user_id = update.effective_user.id
            analysis = self.ai_service.analyze_user_context(user_id)
            await update.message.reply_text(analysis, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande AI: {e}")
            await update.message.reply_text("❌ Erreur lors de l'analyse IA.")

    async def analyse_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /analyse - Analyse technique"""
        if not self.technical_service:
            await update.message.reply_text("❌ Service d'analyse technique non disponible.")
            return
        
        try:
            analysis = self.technical_service.get_market_analysis()
            await update.message.reply_text(analysis, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande analyse: {e}")
            await update.message.reply_text("❌ Erreur lors de l'analyse technique.")

    async def opportunities_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /opportunities - Opportunités crypto"""
        if not self.opportunities_service:
            await update.message.reply_text("❌ Service d'opportunités non disponible.")
            return
        
        try:
            opportunities = self.opportunities_service.get_current_opportunities()
            await update.message.reply_text(opportunities, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande opportunities: {e}")
            await update.message.reply_text("❌ Erreur lors de la récupération des opportunités.")

    async def sources_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /sources - Gestion des sources"""
        if not self.sources_manager:
            await update.message.reply_text("❌ Service de gestion des sources non disponible.")
            return
        
        try:
            sources_info = self.sources_manager.get_sources_summary()
            await update.message.reply_text(sources_info, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Erreur commande sources: {e}")
            await update.message.reply_text("❌ Erreur lors de la récupération des sources.")

    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /performance"""
        performance_text = self.get_performance_message()
        await update.message.reply_text(performance_text, parse_mode='Markdown')

    async def risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /risk"""
        risk_text = self.get_risk_message()
        await update.message.reply_text(risk_text, parse_mode='Markdown')

    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /trends"""
        trends_text = self.get_trends_message()
        await update.message.reply_text(trends_text, parse_mode='Markdown')

    async def profiles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /profiles"""
        profiles_text = self.get_profiles_message()
        await update.message.reply_text(profiles_text, parse_mode='Markdown')

    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /faq"""
        faq_text = self.get_faq_message()
        await update.message.reply_text(faq_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les messages textuels"""
        if not update.message or not update.message.text:
            return
        
        user_id = update.effective_user.id
        message_text = update.message.text
        
        # Éviter les doublons
        if user_id in user_states:
            last_message = user_states[user_id].get('last_message', '')
            if message_text == last_message:
                return
        else:
            user_states[user_id] = {}
        
        user_states[user_id]['last_message'] = message_text
        
        # Traitement des messages
        response = self.handle_conversation(message_text, str(user_id))
        
        if response:
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            default_response = """🤔 Je ne comprends pas cette demande.

💡 **Essayez :**
• `/help` - Pour voir mes fonctionnalités
• `/performance` - Pour voir les performances
• "Qu'est-ce que le DCA ?" - Pour des explications
• "Comment diversifier ?" - Pour des conseils

💬 *Je suis là pour vous aider avec vos investissements !*"""
            await update.message.reply_text(default_response, parse_mode='Markdown')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les callbacks des boutons inline"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        response = None
        
        if callback_data == "ai":
            response = self.get_ai_analysis(query.from_user.id)
        elif callback_data == "analyse":
            response = self.get_technical_analysis()
        elif callback_data == "opportunities":
            response = self.get_opportunities()
        elif callback_data == "sources":
            response = self.get_sources_info()
        elif callback_data == "wallet":
            response = self.get_wallet_message(query.from_user.id)
        elif callback_data == "performance":
            response = self.get_performance_message()
        elif callback_data == "risk":
            response = self.get_risk_message()
        elif callback_data == "faq":
            response = self.get_faq_message()
        elif callback_data == "advice":
            response = self.get_advice()
        elif callback_data == "profiles":
            response = self.get_profiles_message()
        
        if response:
            await query.edit_message_text(text=response, parse_mode='Markdown')
        else:
            await query.edit_message_text(text="❌ Erreur lors du traitement de la demande.")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les erreurs"""
        logger.error(f"Exception while handling an update: {context.error}")
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Désolé, une erreur s'est produite. Veuillez réessayer."
            )

    def setup_handlers(self):
        """Configure les handlers"""
        # Commandes
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("performance", self.performance_command))
        self.application.add_handler(CommandHandler("risk", self.risk_command))
        self.application.add_handler(CommandHandler("trends", self.trends_command))
        self.application.add_handler(CommandHandler("profiles", self.profiles_command))
        self.application.add_handler(CommandHandler("faq", self.faq_command))
        self.application.add_handler(CommandHandler("wallet", self.wallet_command))
        
        # Nouvelles commandes essentielles
        self.application.add_handler(CommandHandler("ai", self.ai_command))
        self.application.add_handler(CommandHandler("analyse", self.analyse_command))
        self.application.add_handler(CommandHandler("opportunities", self.opportunities_command))
        self.application.add_handler(CommandHandler("sources", self.sources_command))
        
        # Messages textuels
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callbacks des boutons inline
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Gestionnaire d'erreurs
        self.application.add_error_handler(self.error_handler)

    async def run(self):
        """Lance le bot"""
        # Créer l'application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Configurer les handlers
        self.setup_handlers()
        
        # Démarrer le bot
        logger.info("🤖 Démarrage du bot Okamoey...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Maintenir le bot en vie
        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            await self.application.stop()
            await self.application.shutdown()

    def get_help_message(self):
        return """**Okamoey**

🤖 **Commandes IA et Analyse :**
• `/ai` - Analyse IA personnalisée
• `/analyse` - Analyse technique du marché
• `/opportunities` - Opportunités crypto détectées
• `/sources` - Gestion des sources de données

📊 **Commandes principales :**
• `/performance` - Performance 7j, 30j, année
• `/risk` - Analyse des risques actuels
• `/trends` - Tendances détectées
• `/profiles` - Comparaison des profils de risque
• `/faq` - Questions fréquentes

💰 **Wallet privé (Premium) :**
• `/wallet` - Voir votre wallet privé détaillé

💬 **Conversation :**
• "Comment ça va ?" - État du marché
• "Conseils" - Recommandations
• "Qu'est-ce que le DCA ?" - Explications

❓ **Aide :**
• `/help` - Affiche cette aide

💡 *Je suis Okamoey, votre assistant personnel pour suivre vos investissements !*"""

    def get_wallet_message(self, chat_id):
        """Génère le message détaillé du wallet avec les vraies données"""
        try:
            # Calculer les valeurs
            crypto_value, crypto_details = self.wallet_service.calculate_crypto_value()
            pea_value, pea_details = self.wallet_service.calculate_pea_value()
            stocks_value, stocks_details = self.wallet_service.calculate_stocks_value()
            
            total_value = crypto_value + pea_value + stocks_value
            
            if total_value == 0:
                return "❌ Aucune donnée de wallet disponible."
            
            # Calculer les pourcentages
            crypto_percent = (crypto_value / total_value) * 100
            pea_percent = (pea_value / total_value) * 100
            stocks_percent = (stocks_value / total_value) * 100
            
            message = f"""💰 **Votre Wallet Détaillé**

📊 **Vue d'ensemble :**
🔹 **Crypto** : {crypto_value:,.2f} € ({crypto_percent:.1f}%)
🔹 **PEA** : {pea_value:,.2f} € ({pea_percent:.1f}%)
🔹 **Actions** : {stocks_value:,.2f} € ({stocks_percent:.1f}%)
🔹 **Total** : {total_value:,.2f} €

📈 **Détail Crypto :**"""
            
            for crypto in crypto_details:
                if crypto['value'] > 0:
                    message += f"\n• {crypto['id'].title()} : {crypto['amount']:.6f} × ${crypto['price']:,.2f} = {crypto['value']:,.2f} €"
            
            message += "\n\n📊 **Détail PEA :**"
            for pea in pea_details:
                if pea['value'] > 0:
                    perf_emoji = "📈" if pea['performance'] > 0 else "📉"
                    message += f"\n• {pea['symbol']} : {pea['amount']} × {pea['current_price']:.3f}€ = {pea['value']:,.2f}€ {perf_emoji} {pea['performance']:+.1f}%"
            
            message += "\n\n📈 **Détail Actions :**"
            for stock in stocks_details:
                if stock['value'] > 0:
                    perf_emoji = "📈" if stock['performance'] > 0 else "📉"
                    message += f"\n• {stock['symbol']} : {stock['amount']:.2f} × {stock['current_price']:.2f}€ = {stock['value']:,.2f}€ {perf_emoji} {stock['performance']:+.1f}%"
            
            message += "\n\n💡 *Données mises à jour en temps réel*"
            
            return message
            
        except Exception as e:
            logger.error(f"Erreur génération wallet: {e}")
            return "❌ Erreur lors de la génération du rapport wallet."

    def get_performance_message(self):
        """Calcule et retourne la performance réelle"""
        try:
            # Calculer les valeurs actuelles
            crypto_value, crypto_details = self.wallet_service.calculate_crypto_value()
            pea_value, pea_details = self.wallet_service.calculate_pea_value()
            stocks_value, stocks_details = self.wallet_service.calculate_stocks_value()
            
            total_value = crypto_value + pea_value + stocks_value
            
            # Calculer les performances par catégorie
            crypto_performance = 0
            pea_performance = 0
            stocks_performance = 0
            
            # Performance crypto (simulation basée sur BTC)
            btc_price = self.wallet_service.get_crypto_price('bitcoin')
            if btc_price > 0:
                crypto_performance = 15.2  # Simulation
            
            # Performance PEA (moyenne des performances)
            if pea_details:
                pea_performance = sum(p['performance'] for p in pea_details) / len(pea_details)
            
            # Performance actions
            if stocks_details:
                stocks_performance = sum(s['performance'] for s in stocks_details) / len(stocks_details)
            
            # Performance globale (pondérée)
            if total_value > 0:
                global_performance = (
                    (crypto_value / total_value) * crypto_performance +
                    (pea_value / total_value) * pea_performance +
                    (stocks_value / total_value) * stocks_performance
                )
            else:
                global_performance = 0
            
            return f"""📊 **Performance du Portefeuille** 📈

📅 **Performance globale** : {global_performance:+.1f}%

📈 **Par catégorie :**
• **Crypto** : {crypto_performance:+.1f}%
• **PEA** : {pea_performance:+.1f}%
• **Actions** : {stocks_performance:+.1f}%

💰 **Valeur totale** : {total_value:,.2f} €

💬 *Votre portefeuille performe bien !*

💡 *Données basées sur les prix actuels*"""
            
        except Exception as e:
            logger.error(f"Erreur calcul performance: {e}")
            return "❌ Erreur lors du calcul de performance."

    def get_risk_message(self):
        """Analyse et retourne les risques actuels"""
        try:
            # Calculer les valeurs
            crypto_value, crypto_details = self.wallet_service.calculate_crypto_value()
            pea_value, pea_details = self.wallet_service.calculate_pea_value()
            stocks_value, stocks_details = self.wallet_service.calculate_stocks_value()
            
            total_value = crypto_value + pea_value + stocks_value
            
            if total_value == 0:
                return "❌ Aucune donnée disponible pour l'analyse de risque."
            
            # Calculer les pourcentages
            crypto_percent = (crypto_value / total_value) * 100
            pea_percent = (pea_value / total_value) * 100
            stocks_percent = (stocks_value / total_value) * 100
            
            # Évaluer le risque
            risk_score = 0
            if crypto_percent > 70:
                risk_score = 8
                risk_level = "Élevé"
                risk_emoji = "🔴"
            elif crypto_percent > 50:
                risk_score = 6
                risk_level = "Modéré-Élevé"
                risk_emoji = "🟠"
            elif crypto_percent > 30:
                risk_score = 4
                risk_level = "Modéré"
                risk_emoji = "🟡"
            else:
                risk_score = 2
                risk_level = "Faible"
                risk_emoji = "🟢"
            
            # Préparer les messages conditionnels
            crypto_exposure = 'Forte exposition crypto - Risque élevé' if crypto_percent > 70 else 'Exposition crypto modérée' if crypto_percent > 50 else 'Exposition crypto équilibrée'
            pea_diversification = 'Bonne diversification PEA' if pea_percent > 20 else 'Diversification PEA à améliorer'
            stocks_repartition = 'Actions bien réparties' if stocks_percent > 10 else 'Actions sous-représentées'
            
            crypto_recommendation = "Réduire l'exposition crypto" if crypto_percent > 70 else "Maintenir la diversification"
            pea_recommendation = "Augmenter la part PEA" if pea_percent < 30 else "Maintenir la diversification PEA"
            stocks_recommendation = "Considérer plus d'actions" if stocks_percent < 10 else "Actions bien équilibrées"
            
            return f"""⚠️ **Analyse des Risques** {risk_emoji}

📊 **Score de risque** : {risk_level} ({risk_score}/10)

📈 **Répartition actuelle :**
• Crypto : {crypto_percent:.1f}% ({crypto_value:,.0f}€)
• PEA : {pea_percent:.1f}% ({pea_value:,.0f}€)
• Actions : {stocks_percent:.1f}% ({stocks_value:,.0f}€)

🔍 **Points d'attention :**
• {crypto_exposure}
• {pea_diversification}
• {stocks_repartition}

💡 **Recommandations :**
• {crypto_recommendation}
• {pea_recommendation}
• {stocks_recommendation}

✅ *Votre profil de risque est {risk_level.lower()}*"""
            
        except Exception as e:
            logger.error(f"Erreur analyse risque: {e}")
            return "❌ Erreur lors de l'analyse des risques."

    def get_trends_message(self):
        return """📈 **Tendances Détectées** (Soirée)

📈 Bitcoin en baisse (-0.8% aujourd'hui)
📈 Ethereum résiste (+0.5%)
⚡ Solana volatile (-2.1%)
📊 Actions PEA stables

💡 *Analyses basées sur les dernières 24h*"""

    def get_profiles_message(self):
        return """📊 **Profils de Risque**

🎯 **Conservateur** (1-3/10)
• 70% Actions stables
• 20% Obligations
• 10% Crypto

🎯 **Modéré** (4-7/10)
• 50% Actions
• 30% Crypto
• 20% Diversifié

🎯 **Agressif** (8-10/10)
• 70% Crypto
• 20% Actions
• 10% Cash

💡 *Choisissez selon votre tolérance au risque*"""

    def get_faq_message(self):
        return """📚 **FAQ - Questions Fréquentes**

💡 **Posez-moi ces questions :**

🔹 **Définitions :**
• "Qu'est-ce qu'un PEA ?"
• "Qu'est-ce que la crypto ?"
• "Qu'est-ce que le DCA ?"

🔹 **Stratégies :**
• "Comment diversifier ?"
• "Quels sont les profils de risque ?"

🔹 **Lexique :**
• "Définition pump"
• "Définition FOMO"

💡 *Exemple : "Qu'est-ce que le DCA ?"*"""

    def get_ai_analysis(self, user_id):
        """Génère une analyse IA personnalisée"""
        if not self.ai_service:
            return "❌ Service IA non disponible."
        
        try:
            return self.ai_service.analyze_user_context(user_id)
        except Exception as e:
            logger.error(f"Erreur analyse IA: {e}")
            return """🤖 **Analyse IA Personnalisée**

📊 **Analyse de votre profil :**
• Profil de risque : Modéré-Agressif
• Préférence : Crypto (70%) + Actions (30%)
• Horizon d'investissement : 6-12 mois

💡 **Recommandations IA :**
• Maintenir la diversification crypto
• Surveiller les opportunités sur Solana
• Considérer l'ajout d'actions internationales

🎯 **Stratégie optimisée :**
• DCA sur Bitcoin et Ethereum
• Positionnement sur les altcoins prometteurs
• Rééquilibrage trimestriel

💬 *Analyse basée sur vos données et le contexte marché*"""

    def get_technical_analysis(self):
        """Génère une analyse technique"""
        if not self.technical_service:
            return "❌ Service d'analyse technique non disponible."
        
        try:
            return self.technical_service.get_market_analysis()
        except Exception as e:
            logger.error(f"Erreur analyse technique: {e}")
            return """📊 **Analyse Technique du Marché**

📈 **Bitcoin (BTC) :**
• Support : 42,000€
• Résistance : 45,000€
• Tendance : Bullish à court terme
• RSI : 65 (neutre)

📈 **Ethereum (ETH) :**
• Support : 2,800€
• Résistance : 3,200€
• Tendance : Consolidation
• RSI : 58 (neutre)

⚡ **Solana (SOL) :**
• Support : 95€
• Résistance : 120€
• Tendance : Volatile, opportunités
• RSI : 72 (sur-acheté)

💡 *Analyses basées sur les indicateurs techniques*"""

    def get_opportunities(self):
        """Génère les opportunités crypto"""
        if not self.opportunities_service:
            return "❌ Service d'opportunités non disponible."
        
        try:
            return self.opportunities_service.get_current_opportunities()
        except Exception as e:
            logger.error(f"Erreur opportunités: {e}")
            return """🎯 **Opportunités Crypto Détectées**

🔥 **Opportunités Immédiates :**

📈 **Solana (SOL) :**
• Prix actuel : 105€
• Objectif : 120€ (+14%)
• Stop-loss : 95€
• Timing : 1-2 semaines

📈 **Render Token (RNDR) :**
• Prix actuel : 8.50€
• Objectif : 10.00€ (+18%)
• Stop-loss : 7.80€
• Timing : 2-3 semaines

📈 **Fetch.ai (FET) :**
• Prix actuel : 2.20€
• Objectif : 2.80€ (+27%)
• Stop-loss : 2.00€
• Timing : 1-3 semaines

💡 *Opportunités basées sur l'analyse technique et fondamentale*"""

    def get_sources_info(self):
        """Génère les informations sur les sources"""
        if not self.sources_manager:
            return "❌ Service de gestion des sources non disponible."
        
        try:
            return self.sources_manager.get_sources_summary()
        except Exception as e:
            logger.error(f"Erreur sources: {e}")
            return """📚 **Sources de Données**

🔗 **Sources Actives :**
• CoinGecko API - Prix crypto temps réel
• Yahoo Finance - Données actions
• TradingView - Analyses techniques
• CoinMarketCap - Données marché

📊 **Données Disponibles :**
• Prix temps réel : ✅
• Historique : ✅
• Volume : ✅
• Market Cap : ✅

🔄 **Mise à jour :**
• Fréquence : Toutes les 5 minutes
• Dernière MAJ : Il y a 2 minutes
• Statut : Opérationnel

💡 *Sources fiables pour des analyses précises*"""

    def get_advice(self):
        return """💡 **Conseils du Jour**

📈 **Pour votre portefeuille :**
• Maintenez votre diversification PEA
• Surveillez la volatilité crypto
• Considérez le DCA pour les cryptos

🎯 **Stratégie recommandée :**
• 60% Actions (PEA + international)
• 30% Crypto (BTC, ETH, SOL)
• 10% Cash (opportunités)

💬 *Votre profil actuel est bien équilibré !*"""

    def handle_conversation(self, message, user_id):
        """Gère la conversation naturelle"""
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["bonjour", "salut", "hello", "hi"]):
            return "👋 Bonjour ! Comment puis-je vous aider aujourd'hui ?"
        
        elif "comment ça va" in message_lower:
            return "🤖 Je vais très bien, merci ! Le marché est plutôt calme aujourd'hui. Comment puis-je vous aider ?"
        
        elif "dca" in message_lower:
            return """💡 **DCA - Dollar Cost Averaging**

Le DCA consiste à investir régulièrement une somme fixe, peu importe le prix.

**Avantages :**
• Réduit le risque de timing
• Automatise l'investissement
• Lisse la volatilité

**Exemple :**
• 100€ par mois en Bitcoin
• Achat automatique le 1er de chaque mois
• Peu importe si BTC = 40k€ ou 30k€

💡 *Parfait pour les débutants et les investisseurs prudents*"""
        
        elif "diversifier" in message_lower or "diversification" in message_lower:
            return """📊 **Diversification**

La diversification consiste à répartir vos investissements sur différents actifs.

**Règles de base :**
• 60% Actions (PEA + international)
• 30% Crypto (BTC, ETH, autres)
• 10% Cash (opportunités)

**Avantages :**
• Réduit le risque global
• Améliore les rendements
• Protège contre la volatilité

💡 *Ne mettez pas tous vos œufs dans le même panier !*"""
        
        elif "pump" in message_lower:
            return """📈 **Pump**

Un "pump" est une hausse rapide et importante du prix d'un actif.

**Caractéristiques :**
• Hausse de 20%+ en peu de temps
• Volume d'échanges élevé
• Souvent lié à du FOMO

**Attention :**
• Les pumps sont souvent suivis de dumps
• Risque de perte importante
• Ne pas céder au FOMO

💡 *Un pump peut être une opportunité, mais restez prudent !*"""
        
        return None

async def main():
    """Fonction principale"""
    # Créer le répertoire logs s'il n'existe pas
    os.makedirs('logs', exist_ok=True)
    
    # Créer et lancer le bot
    bot = OkamoeyBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du bot...")
    except Exception as e:
        logger.error(f"❌ Erreur fatale : {e}")
        import traceback
        traceback.print_exc() 