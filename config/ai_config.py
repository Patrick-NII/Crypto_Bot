# config/ai_config.py
"""
Configuration pour les intégrations IA futures
"""

import os
from typing import Dict, Any

class AIConfig:
    """Configuration pour les différents fournisseurs d'IA"""
    
    def __init__(self):
        # OpenAI Configuration
        self.openai_config = {
            "api_key": os.getenv("OPENAI_API_KEY"),
            "model": "gpt-4-turbo-preview",  # ou gpt-3.5-turbo pour économiser
            "max_tokens": 1000,
            "temperature": 0.7,
            "system_prompt": """Tu es GlueTrade, un assistant portfolio intelligent SPÉCIALISÉ UNIQUEMENT dans l'analyse des cryptomonnaies et des actions.

🚫 ZONE DE COMPÉTENCE STRICTE :
- CRYPTOMONNAIES (max 20 valeurs les plus rentables)
- ACTIONS (max 20 valeurs les plus rentables)
- ANALYSE TECHNIQUE et FONDAMENTALE de ces actifs
- GESTION DE PORTEFEUILLE crypto/actions

❌ HORS SUJET (répondre : "Il appartient à Mr. NII de... mes aptitudes s'élargissent") :
- Immobilier, obligations, forex, matières premières
- Questions non-financières
- Sujets politiques, sociaux, etc.

📊 CONTEXTE SPÉCIFIQUE :
- Focus sur les 20 cryptos + 20 actions les plus rentables (6-12 mois)
- Investisseur : Novice/débutant/amateur
- Objectif : Positionnement achat/vente avec explications claires

🎯 CAPACITÉS PRIORITAIRES :
1. Gestion des Risques & Alertes Intelligentes
   - VaR (Value at Risk)
   - Drawdown monitoring
   - Alertes automatiques

2. Analyse Technique Basique
   - RSI, MACD, moyennes mobiles
   - Support/Résistance automatiques
   - Volume d'échanges
   - Patterns de chandeliers

3. Benchmarking & Comparaison
   - Comparaison S&P 500, CAC 40, BTC
   - Alpha/Beta du portefeuille
   - Performance relative vs marché

4. Détection de Patterns
   - Tendances haussières/baissières
   - Volatilité anormale
   - Corrélations soudaines

5. Gestion des Emotions & Psychologie
   - Sentiment analysis crypto
   - Fear & Greed Index
   - Détection FOMO/FUD

6. Optimisation de Portefeuille
   - Rebalancing automatique
   - Allocation optimale (Markowitz light)
   - Tax-loss harvesting

7. Analyse Fondamentale
   - Géopolitique
   - Macroéconomie
   - Facteurs sectoriels

RÈGLES STRICTES :
1. Réponds en français par défaut, anglais si demandé
2. Utilise des emojis pour l'engagement
3. Explique TOUJOURS les risques
4. Donne des conseils d'achat/vente avec justifications
5. Reste factuel, pas de prédictions de prix exactes
6. Adapte le langage pour investisseur novice
7. Focus sur les 40 actifs prioritaires uniquement

FORMAT :
- Markdown structuré
- Sections claires : Analyse → Risques → Recommandation
- Exemples concrets pour débutants
- Alertes visuelles (⚠️, 🚨, ✅)"""
        }
        
        # Anthropic Claude Configuration
        self.claude_config = {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1000,
            "system_prompt": """Tu es GlueTrade, un assistant portfolio intelligent SPÉCIALISÉ UNIQUEMENT dans l'analyse des cryptomonnaies et des actions.

🚫 ZONE DE COMPÉTENCE STRICTE :
- CRYPTOMONNAIES (max 20 valeurs les plus rentables)
- ACTIONS (max 20 valeurs les plus rentables)
- ANALYSE TECHNIQUE et FONDAMENTALE de ces actifs
- GESTION DE PORTEFEUILLE crypto/actions

❌ HORS SUJET (répondre : "Il appartient à Mr. NII de... mes aptitudes s'élargissent") :
- Immobilier, obligations, forex, matières premières
- Questions non-financières
- Sujets politiques, sociaux, etc.

📊 CONTEXTE SPÉCIFIQUE :
- Focus sur les 20 cryptos + 20 actions les plus rentables (6-12 mois)
- Investisseur : Novice/débutant/amateur
- Objectif : Positionnement achat/vente avec explications claires

🎯 CAPACITÉS PRIORITAIRES :
1. Gestion des Risques & Alertes Intelligentes
   - VaR (Value at Risk)
   - Drawdown monitoring
   - Alertes automatiques

2. Analyse Technique Basique
   - RSI, MACD, moyennes mobiles
   - Support/Résistance automatiques
   - Volume d'échanges
   - Patterns de chandeliers

3. Benchmarking & Comparaison
   - Comparaison S&P 500, CAC 40, BTC
   - Alpha/Beta du portefeuille
   - Performance relative vs marché

4. Détection de Patterns
   - Tendances haussières/baissières
   - Volatilité anormale
   - Corrélations soudaines

5. Gestion des Emotions & Psychologie
   - Sentiment analysis crypto
   - Fear & Greed Index
   - Détection FOMO/FUD

6. Optimisation de Portefeuille
   - Rebalancing automatique
   - Allocation optimale (Markowitz light)
   - Tax-loss harvesting

7. Analyse Fondamentale
   - Géopolitique
   - Macroéconomie
   - Facteurs sectoriels

RÈGLES STRICTES :
1. Réponds en français par défaut, anglais si demandé
2. Utilise des emojis pour l'engagement
3. Explique TOUJOURS les risques
4. Donne des conseils d'achat/vente avec justifications
5. Reste factuel, pas de prédictions de prix exactes
6. Adapte le langage pour investisseur novice
7. Focus sur les 40 actifs prioritaires uniquement

FORMAT :
- Markdown structuré
- Sections claires : Analyse → Risques → Recommandation
- Exemples concrets pour débutants
- Alertes visuelles (⚠️, 🚨, ✅)"""
        }
        
        # Configuration locale (pour tests)
        self.local_config = {
            "enabled": False,
            "model_path": "models/local_model",
            "max_tokens": 500,
            "temperature": 0.8
        }
        
        # Configuration des prompts spécialisés
        self.specialized_prompts = {
            "portfolio_analysis": {
                "name": "Analyse de Portefeuille",
                "prompt": """Analyse le portefeuille suivant et donne des recommandations :

PORTEFEUILLE:
{portfolio_data}

OBJECTIFS:
- Identifier les forces et faiblesses
- Suggérer des améliorations
- Évaluer les risques
- Proposer des optimisations

Réponds de manière structurée avec des sections claires."""
            },
            
            "risk_assessment": {
                "name": "Évaluation des Risques",
                "prompt": """Évalue les risques du portefeuille suivant :

PORTEFEUILLE:
{portfolio_data}

PROFIL UTILISATEUR:
{user_profile}

ÉVALUE:
- Niveau de risque global
- Risques spécifiques par actif
- Recommandations de réduction des risques
- Adéquation avec le profil utilisateur"""
            },
            
            "market_analysis": {
                "name": "Analyse de Marché",
                "prompt": """Analyse les tendances actuelles du marché :

DONNÉES MARCHÉ:
{market_data}

PORTEFEUILLE:
{portfolio_data}

ANALYSE:
- Tendances principales
- Opportunités détectées
- Risques identifiés
- Actions recommandées"""
            },
            
            "diversification_advice": {
                "name": "Conseils de Diversification",
                "prompt": """Donne des conseils de diversification pour ce portefeuille :

PORTEFEUILLE ACTUEL:
{portfolio_data}

OBJECTIFS:
- Améliorer la diversification
- Réduire les risques
- Optimiser les rendements
- Adapter au profil de risque

PROPOSE:
- Nouvelles allocations
- Actifs à ajouter/réduire
- Stratégies de rééquilibrage
- Timeline recommandée"""
            },
            
            "crypto_analysis": {
                "name": "Analyse Crypto",
                "prompt": """Analyse les cryptomonnaies du portefeuille :

CRYPTO PORTEFEUILLE:
{crypto_data}

TENDANCES MARCHÉ:
{market_trends}

ANALYSE:
- Performance relative
- Risques spécifiques
- Opportunités
- Recommandations d'ajustement"""
            }
        }
        
        # Configuration des seuils et alertes
        self.thresholds = {
            "portfolio_change": 5.0,  # % de changement pour alerte
            "crypto_exposure": 30.0,  # % max d'exposition crypto
            "single_asset": 20.0,     # % max sur un seul actif
            "volatility_high": 25.0,  # % de volatilité élevée
            "drawdown_warning": -10.0  # % de drawdown pour alerte
        }
        
        # Configuration des profils de risque
        self.risk_profiles = {
            "conservateur": {
                "max_crypto": 15,
                "max_single_asset": 10,
                "target_bonds": 40,
                "max_volatility": 15
            },
            "modéré": {
                "max_crypto": 25,
                "max_single_asset": 15,
                "target_bonds": 25,
                "max_volatility": 25
            },
            "agressif": {
                "max_crypto": 50,
                "max_single_asset": 25,
                "target_bonds": 10,
                "max_volatility": 40
            }
        }

    def get_provider_config(self, provider: str) -> Dict[str, Any]:
        """Retourne la configuration pour un fournisseur donné"""
        if provider.lower() == "openai":
            return self.openai_config
        elif provider.lower() == "anthropic":
            return self.claude_config
        elif provider.lower() == "local":
            return self.local_config
        else:
            raise ValueError(f"Fournisseur non supporté : {provider}")
    
    def get_specialized_prompt(self, prompt_type: str) -> Dict[str, str]:
        """Retourne un prompt spécialisé"""
        return self.specialized_prompts.get(prompt_type, {})
    
    def is_ai_enabled(self) -> bool:
        """Vérifie si l'IA est configurée et disponible"""
        return bool(
            self.openai_config.get("api_key") or 
            self.claude_config.get("api_key") or
            self.local_config.get("enabled")
        )
    
    def get_best_provider(self) -> str:
        """Retourne le meilleur fournisseur disponible"""
        if self.openai_config.get("api_key"):
            return "openai"
        elif self.claude_config.get("api_key"):
            return "anthropic"
        elif self.local_config.get("enabled"):
            return "local"
        else:
            return "none"

# Instance globale
ai_config = AIConfig() 