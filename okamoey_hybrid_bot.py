#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Okamoey Hybrid Bot - Assistant Portfolio Intelligent
Version hybride avec chatbot basique + préparation IA
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from modules.telegram_commands import *
from modules.chatbot_basic import BasicChatbot
from modules.risk_profiles import RiskProfiles

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

# Configuration
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')

# Initialiser les modules
basic_chatbot = BasicChatbot()
risk_profiles = RiskProfiles()

# État global pour éviter les doublons
user_states = {}

class OkamoeyHybridBot:
    def __init__(self):
        self.application = None
        self.basic_chatbot = BasicChatbot()
        self.risk_profiles = RiskProfiles()
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /start"""
        user = update.effective_user
        welcome_message = f"""🤖 **Bienvenue {user.first_name} !**

Je suis **Okamoey**, votre assistant portfolio intelligent.

📊 **Je peux vous aider avec :**
• Analyse de votre portefeuille
• Conseils de diversification
• Surveillance des tendances
• Explications financières
• Profils de risque personnalisés

💡 **Commandes principales :**
• `/help` - Aide complète
• `/portfolio` - Votre portefeuille
• `/performance` - Performance
• `/risk` - Analyse des risques

💬 **Ou parlez-moi naturellement :**
• "Comment ça va ?"
• "Qu'est-ce que le DCA ?"
• "Conseils pour diversifier"

🚀 *Prêt à optimiser vos investissements ?*"""
        
        # Créer des boutons inline
        keyboard = [
            [
                InlineKeyboardButton("📊 Mon Portfolio", callback_data="portfolio"),
                InlineKeyboardButton("📈 Performance", callback_data="performance")
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
        help_text = get_help_message()
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def portfolio_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /portfolio"""
        portfolio_text = get_portfolio_summary()
        await update.message.reply_text(portfolio_text, parse_mode='Markdown')

    async def performance_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /performance"""
        performance_text = get_performance_message()
        await update.message.reply_text(performance_text, parse_mode='Markdown')

    async def risk_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /risk"""
        risk_text = get_risk_message()
        await update.message.reply_text(risk_text, parse_mode='Markdown')

    async def trends_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /trends"""
        trends_text = get_trends_message()
        await update.message.reply_text(trends_text, parse_mode='Markdown')

    async def profiles_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /profiles"""
        profiles_text = get_profiles_message()
        await update.message.reply_text(profiles_text, parse_mode='Markdown')

    async def faq_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Commande /faq"""
        faq_text = get_faq_message()
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
        
        # Traiter le message
        response = None
        
        # Vérifier si c'est une commande
        if message_text.startswith('/'):
            command = message_text.split()[0]
            response = handle_command(command)
        else:
            # Traiter comme conversation naturelle
            response = handle_conversation(message_text, str(user_id))
        
        if response:
            await update.message.reply_text(response, parse_mode='Markdown')
        else:
            # Réponse par défaut si aucune correspondance
            default_response = """🤔 Je ne comprends pas cette demande.

💡 **Essayez :**
• `/help` - Pour voir mes fonctionnalités
• "Qu'est-ce que le DCA ?" - Pour des explications
• "Comment diversifier ?" - Pour des conseils
• `/portfolio` - Pour voir votre portefeuille

💬 *Je suis là pour vous aider avec vos investissements !*"""
            await update.message.reply_text(default_response, parse_mode='Markdown')

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gère les callbacks des boutons inline"""
        query = update.callback_query
        await query.answer()
        
        callback_data = query.data
        
        response = None
        
        if callback_data == "portfolio":
            response = get_portfolio_summary()
        elif callback_data == "performance":
            response = get_performance_message()
        elif callback_data == "risk":
            response = get_risk_message()
        elif callback_data == "faq":
            response = get_faq_message()
        elif callback_data == "advice":
            response = get_advice()
        elif callback_data == "profiles":
            response = get_profiles_message()
        
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
        self.application.add_handler(CommandHandler("portfolio", self.portfolio_command))
        self.application.add_handler(CommandHandler("performance", self.performance_command))
        self.application.add_handler(CommandHandler("risk", self.risk_command))
        self.application.add_handler(CommandHandler("trends", self.trends_command))
        self.application.add_handler(CommandHandler("profiles", self.profiles_command))
        self.application.add_handler(CommandHandler("faq", self.faq_command))
        
        # Messages textuels
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Callbacks des boutons inline
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
        # Gestionnaire d'erreurs
        self.application.add_error_handler(self.error_handler)

    async def run(self):
        """Lance le bot"""
        if not BOT_TOKEN:
            logger.error("Token du bot non trouvé dans les variables d'environnement")
            return
        
        # Créer l'application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Configurer les handlers
        self.setup_handlers()
        
        # Démarrer le bot
        logger.info("🤖 Démarrage du bot Okamoey Hybrid...")
        await self.application.initialize()
        await self.application.start()
        await self.application.run_polling()

async def main():
    """Fonction principale"""
    # Créer le répertoire logs s'il n'existe pas
    os.makedirs('logs', exist_ok=True)
    
    # Créer et lancer le bot
    bot = OkamoeyHybridBot()
    await bot.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 Arrêt du bot...")
    except Exception as e:
        logger.error(f"❌ Erreur fatale : {e}") 