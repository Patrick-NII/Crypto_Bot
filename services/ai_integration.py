# modules/ai_integration.py
"""
Module d'intégration IA pour analyses poussées
Utilise OpenAI GPT pour analyses contextuelles
"""

import os
import json
import openai
from datetime import datetime
from typing import Dict, List, Optional
try:
    from config.ai_config import ai_config
except ImportError:
    # Fallback si le module n'existe pas
    ai_config = None
from modules.priority_assets import priority_assets
from modules.technical_analysis import technical_analysis
from modules.sources_manager import sources_manager
from dotenv import load_dotenv

# Charger automatiquement les variables d'environnement depuis .env
load_dotenv()

class AIIntegration:
    def __init__(self):
        self.client = None
        self.is_available = False
        self.initialize_openai()
        
    def initialize_openai(self):
        """Initialise la connexion OpenAI"""
        try:
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                openai.api_key = api_key
                self.client = openai.OpenAI(api_key=api_key)
                self.is_available = True
                print("✅ OpenAI API initialisée avec succès")
            else:
                print("⚠️ Clé OpenAI API non trouvée dans .env")
                self.is_available = False
        except Exception as e:
            print(f"❌ Erreur initialisation OpenAI: {e}")
            self.is_available = False
    
    def get_portfolio_context(self) -> Dict:
        """Récupère le contexte du portefeuille actuel"""
        try:
            # Lire les données du portefeuille
            with open("data/wallet_crypto.json", "r") as f:
                crypto_data = json.load(f)
            
            with open("data/wallet_pea.json", "r") as f:
                pea_data = json.load(f)
            
            # Calculer les totaux
            total_crypto = 2850.0  # Valeur simulée
            total_pea = 0
            pea_assets = []
            
            for ticker, data in pea_data.items():
                amount = data.get('amount', 0)
                pru = data.get('pru', 0)
                current_value = amount * pru * 1.2
                total_pea += current_value
                pea_assets.append({
                    "ticker": ticker,
                    "amount": amount,
                    "pru": pru,
                    "current_value": current_value
                })
            
            total_portfolio = total_crypto + total_pea
            
            # Analyser les actifs prioritaires
            priority_crypto = priority_assets.get_top_crypto(10)
            priority_stocks = priority_assets.get_top_stocks(10)
            
            # Analyse technique des actifs prioritaires
            technical_signals = {}
            for crypto in priority_crypto[:5]:  # Top 5 crypto
                signals = technical_analysis.get_technical_signals(crypto['symbol'])
                if "error" not in signals:
                    technical_signals[crypto['symbol']] = signals
            
            for stock in priority_stocks[:5]:  # Top 5 actions
                signals = technical_analysis.get_technical_signals(stock['symbol'])
                if "error" not in signals:
                    technical_signals[stock['symbol']] = signals
            
            return {
                "total_value": total_portfolio,
                "crypto_value": total_crypto,
                "pea_value": total_pea,
                "crypto_percent": (total_crypto / total_portfolio) * 100 if total_portfolio > 0 else 0,
                "pea_percent": (total_pea / total_portfolio) * 100 if total_portfolio > 0 else 0,
                "pea_assets": pea_assets,
                "priority_assets": {
                    "crypto": priority_crypto,
                    "stocks": priority_stocks
                },
                "technical_analysis": technical_signals,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"❌ Erreur récupération contexte portefeuille: {e}")
            return {}
    
    def analyze_with_ai(self, user_question: str, context: Dict = None) -> str:
        """Analyse une question avec l'IA"""
        if not self.is_available:
            return "❌ IA non disponible. Utilisez le chatbot basique."
        
        try:
            # Récupérer le contexte si non fourni
            if context is None:
                context = self.get_portfolio_context()
            
            # Rechercher dans les sources RAG
            relevant_sources = sources_manager.search_sources(user_question, limit=3)
            sources_context = ""
            
            if relevant_sources:
                sources_context = "\n\nSOURCES PERTINENTES TROUVÉES:\n"
                for i, source in enumerate(relevant_sources, 1):
                    sources_context += f"{i}. {source['title']} ({source['category']})\n"
                    sources_context += f"   {source['content_preview'][:200]}...\n\n"
            
            # Construire le prompt
            if ai_config:
                system_prompt = ai_config.get_provider_config("openai")["system_prompt"]
            else:
                system_prompt = """Tu es un assistant financier spécialisé dans l'analyse de portefeuilles crypto et actions. 
Tu donnes des conseils précis, structurés et adaptés aux investisseurs novices. 
Tu te concentres uniquement sur les 40 actifs prioritaires (20 crypto + 20 actions) les plus profitables sur 6-12 mois.
Si on te demande autre chose, réponds : "Il appartient à Mr. NII de... mes aptitudes s'élargissent." """
            
            # Ajouter le contexte du portefeuille
            context_prompt = f"""
CONTEXTE PORTEFEUILLE ACTUEL:
- Valeur totale: {context.get('total_value', 0):,.2f}€
- Crypto: {context.get('crypto_percent', 0):.1f}% ({context.get('crypto_value', 0):,.2f}€)
- Actions PEA: {context.get('pea_percent', 0):.1f}% ({context.get('pea_value', 0):,.2f}€)

ACTIFS PRIORITAIRES ANALYSÉS:
{self._format_priority_assets(context)}

ANALYSE TECHNIQUE RÉCENTE:
{self._format_technical_analysis(context)}{sources_context}

QUESTION UTILISATEUR: {user_question}

Réponds de manière structurée avec des sections claires et des recommandations concrètes pour un investisseur novice.
Utilise les sources fournies pour enrichir ton analyse si elles sont pertinentes.
"""
            
            # Appel à l'API OpenAI
            response = self.client.chat.completions.create(
                model="gpt-4-turbo-preview",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": context_prompt}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ Erreur analyse IA: {e}")
            return f"❌ Erreur lors de l'analyse IA: {str(e)}"
    
    def _format_priority_assets(self, context: Dict) -> str:
        """Formate les actifs prioritaires pour l'IA"""
        try:
            crypto = context.get('priority_assets', {}).get('crypto', [])[:5]
            stocks = context.get('priority_assets', {}).get('stocks', [])[:5]
            
            crypto_text = "\n".join([
                f"• {c['symbol']} ({c['name']}) - {c['risk_level']} - Objectif 6m: {c['target_6m']}"
                for c in crypto
            ])
            
            stocks_text = "\n".join([
                f"• {s['symbol']} ({s['name']}) - {s['risk_level']} - Objectif 6m: {s['target_6m']}"
                for s in stocks
            ])
            
            return f"""
TOP 5 CRYPTO:
{crypto_text}

TOP 5 ACTIONS:
{stocks_text}
"""
        except Exception as e:
            return "Erreur formatage actifs prioritaires"
    
    def _format_technical_analysis(self, context: Dict) -> str:
        """Formate l'analyse technique pour l'IA"""
        try:
            analysis = context.get('technical_analysis', {})
            if not analysis:
                return "Aucune analyse technique disponible"
            
            formatted = []
            for symbol, signals in analysis.items():
                if "error" not in signals:
                    formatted.append(
                        f"• {symbol}: {signals.get('overall_signal', 'N/A')} "
                        f"(RSI: {signals.get('rsi', {}).get('value', 'N/A'):.1f}, "
                        f"Prix: {signals.get('current_price', 'N/A'):.2f})"
                    )
            
            return "\n".join(formatted[:10])  # Limiter à 10 actifs
            
        except Exception as e:
            return "Erreur formatage analyse technique"
    
    def get_advanced_portfolio_analysis(self) -> str:
        """Analyse avancée du portefeuille avec IA"""
        if not self.is_available:
            return "❌ IA non disponible pour l'analyse avancée."
        
        try:
            context = self.get_portfolio_context()
            
            prompt = """Analyse mon portefeuille actuel et donne-moi des recommandations détaillées :

1. ÉVALUATION ACTUELLE
- Forces et faiblesses de mon allocation
- Risques identifiés
- Opportunités détectées

2. RECOMMANDATIONS D'OPTIMISATION
- Actifs à ajouter/réduire
- Rééquilibrage suggéré
- Stratégie de DCA

3. SURVEILLANCE
- Actifs à surveiller de près
- Alertes à configurer
- Tendances à anticiper

4. CONSEILS POUR INVESTISSEUR NOVICE
- Points d'attention
- Erreurs à éviter
- Bonnes pratiques

Réponds de manière structurée avec des sections claires."""
            
            return self.analyze_with_ai(prompt, context)
            
        except Exception as e:
            return f"❌ Erreur analyse portefeuille: {str(e)}"
    
    def get_asset_recommendation(self, symbol: str) -> str:
        """Recommandation détaillée pour un actif spécifique"""
        if not self.is_available:
            return "❌ IA non disponible pour les recommandations d'actifs."
        
        try:
            # Vérifier si c'est un actif prioritaire
            if not priority_assets.is_priority_asset(symbol):
                return f"❌ {symbol} n'est pas dans nos 40 actifs prioritaires. Il appartient à Mr. NII de... mes aptitudes s'élargissent."
            
            context = self.get_portfolio_context()
            asset_info = priority_assets.get_asset_info(symbol)
            technical_signals = technical_analysis.get_technical_signals(symbol)
            
            prompt = f"""Analyse détaillée de {symbol} ({asset_info.get('name', 'N/A')}) :

INFORMATIONS ACTIF:
- Catégorie: {asset_info.get('category', 'N/A')}
- Niveau de risque: {asset_info.get('risk_level', 'N/A')}
- Objectif 6 mois: {asset_info.get('target_6m', 'N/A')}
- Objectif 12 mois: {asset_info.get('target_12m', 'N/A')}
- Points d'analyse: {', '.join(asset_info.get('analysis_focus', []))}

SIGNAL TECHNIQUE: {technical_signals.get('overall_signal', 'N/A')}

Donne-moi une recommandation d'achat/vente/attente avec :
1. Justification technique et fondamentale
2. Risques associés
3. Stratégie d'entrée/sortie
4. Conseils pour investisseur novice

Réponds de manière structurée et accessible."""
            
            return self.analyze_with_ai(prompt, context)
            
        except Exception as e:
            return f"❌ Erreur recommandation {symbol}: {str(e)}"
    
    def get_market_insights(self) -> str:
        """Insights de marché avec IA"""
        if not self.is_available:
            return "❌ IA non disponible pour les insights de marché."
        
        try:
            context = self.get_portfolio_context()
            
            prompt = """Analyse l'état actuel du marché et donne-moi des insights :

1. TENDANCES ACTUELLES
- Marché crypto vs actions
- Secteurs en vogue
- Sentiment global

2. OPPORTUNITÉS DÉTECTÉES
- Actifs sous-évalués
- Momentum à suivre
- Corrélations intéressantes

3. RISQUES IDENTIFIÉS
- Volatilité attendue
- Facteurs macroéconomiques
- Événements à surveiller

4. STRATÉGIE RECOMMANDÉE
- Positionnement conseillé
- Timing d'investissement
- Gestion des risques

Réponds de manière structurée avec des recommandations concrètes."""
            
            return self.analyze_with_ai(prompt, context)
            
        except Exception as e:
            return f"❌ Erreur insights marché: {str(e)}"
    
    def get_risk_assessment(self) -> str:
        """Évaluation des risques avec IA"""
        if not self.is_available:
            return "❌ IA non disponible pour l'évaluation des risques."
        
        try:
            context = self.get_portfolio_context()
            
            prompt = """Évalue les risques de mon portefeuille actuel :

1. ANALYSE DES RISQUES
- Exposition par classe d'actifs
- Concentration géographique/sectorielle
- Corrélations entre actifs

2. SCÉNARIOS DE STRESS
- Impact d'une baisse crypto de 50%
- Impact d'une correction actions de 20%
- Gestion de la liquidité

3. RECOMMANDATIONS DE RÉDUCTION DES RISQUES
- Diversification suggérée
- Hedging possible
- Allocation défensive

4. MONITORING
- Indicateurs à surveiller
- Seuils d'alerte
- Plan d'action en cas de crise

Réponds de manière structurée avec des recommandations pratiques."""
            
            return self.analyze_with_ai(prompt, context)
            
        except Exception as e:
            return f"❌ Erreur évaluation risques: {str(e)}"

# Instance globale
ai_integration = AIIntegration() 