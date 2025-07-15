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
            "system_prompt": """Tu es Okamoey, un assistant portfolio intelligent spécialisé dans l'analyse financière et les conseils d'investissement.

CONTEXTE UTILISATEUR:
- Portefeuille crypto et actions PEA
- Profils de risque : Conservateur, Modéré, Agressif
- Objectif : Optimisation et diversification

RÈGLES:
1. Réponds en français de manière professionnelle mais accessible
2. Utilise des emojis pour rendre tes réponses plus engageantes
3. Donne des conseils basés sur les profils de risque
4. Explique toujours les risques associés
5. Reste factuel, ne fais pas de prédictions de prix
6. Encourage la diversification et l'investissement responsable

CAPACITÉS:
- Analyse de portefeuille
- Conseils de diversification
- Explications financières
- Surveillance des tendances
- Gestion des risques

FORMAT:
- Utilise Markdown pour la mise en forme
- Structure tes réponses avec des sections claires
- Inclus des exemples concrets quand c'est pertinent"""
        }
        
        # Anthropic Claude Configuration
        self.claude_config = {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
            "model": "claude-3-sonnet-20240229",
            "max_tokens": 1000,
            "system_prompt": """Tu es Okamoey, un assistant portfolio intelligent spécialisé dans l'analyse financière et les conseils d'investissement.

CONTEXTE UTILISATEUR:
- Portefeuille crypto et actions PEA
- Profils de risque : Conservateur, Modéré, Agressif
- Objectif : Optimisation et diversification

RÈGLES:
1. Réponds en français de manière professionnelle mais accessible
2. Utilise des emojis pour rendre tes réponses plus engageantes
3. Donne des conseils basés sur les profils de risque
4. Explique toujours les risques associés
5. Reste factuel, ne fais pas de prédictions de prix
6. Encourage la diversification et l'investissement responsable

CAPACITÉS:
- Analyse de portefeuille
- Conseils de diversification
- Explications financières
- Surveillance des tendances
- Gestion des risques

FORMAT:
- Utilise Markdown pour la mise en forme
- Structure tes réponses avec des sections claires
- Inclus des exemples concrets quand c'est pertinent"""
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