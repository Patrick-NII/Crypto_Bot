# core/bot/onboarding_handler.py
"""
Gestionnaire d'onboarding avec formulaire interactif pour GlueTrade
"""

import os
import sys
from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path

# Ajouter le répertoire racine au path
sys.path.append(str(Path(__file__).resolve().parent.parent.parent))

from services.user_management.user_service import user_service

class OnboardingHandler:
    """Gestionnaire du processus d'onboarding"""
    
    def __init__(self):
        self.user_service = user_service
        self.onboarding_states = {}  # {user_id: state}
        self.user_data = {}  # {user_id: data}
    
    def start_onboarding(self, user_id: int) -> Dict:
        """Démarre le processus d'onboarding"""
        try:
            # Initialiser l'état
            self.onboarding_states[user_id] = 'experience_level'
            self.user_data[user_id] = {}
            
            message = """📋 **ONBOARDING GLUETRADE**

Bienvenue ! Pour vous offrir des conseils IA pertinents, nous avons besoin de quelques informations.

🔒 **Confidentialité garantie:**
• Vos données sont chiffrées
• Utilisées uniquement pour les conseils IA
• Pas de partage avec des tiers
• Conformité RGPD

📊 **Étape 1/5: Niveau d'expérience**

Quel est votre niveau d'expérience en crypto ?

💡 **Définitions:**
• **Débutant:** Premiers pas, moins de 6 mois
• **Intermédiaire:** 6 mois à 2 ans d'expérience
• **Avancé:** Plus de 2 ans, trading régulier"""
            
            keyboard = [
                [{"text": "🌱 Débutant", "callback_data": "exp_beginner"}],
                [{"text": "📈 Intermédiaire", "callback_data": "exp_intermediate"}],
                [{"text": "🚀 Avancé", "callback_data": "exp_advanced"}],
                [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur démarrage onboarding: {e}")
            return {
                'message': "❌ Erreur lors du démarrage de l'onboarding.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def handle_onboarding_step(self, user_id: int, callback_data: str) -> Dict:
        """Gère une étape de l'onboarding"""
        try:
            current_state = self.onboarding_states.get(user_id)
            
            if not current_state:
                return self._finish_onboarding(user_id)
            
            # Traiter la réponse selon l'état actuel
            if current_state == 'experience_level':
                return self._handle_experience_level(user_id, callback_data)
            elif current_state == 'risk_profile':
                return self._handle_risk_profile(user_id, callback_data)
            elif current_state == 'investment_goals':
                return self._handle_investment_goals(user_id, callback_data)
            elif current_state == 'investment_amount':
                return self._handle_investment_amount(user_id, callback_data)
            elif current_state == 'time_horizon':
                return self._handle_time_horizon(user_id, callback_data)
            else:
                return self._finish_onboarding(user_id)
                
        except Exception as e:
            print(f"Erreur étape onboarding: {e}")
            return {
                'message': "❌ Erreur lors de l'onboarding. Utilisez /start pour recommencer.",
                'keyboard': None,
                'parse_mode': 'Markdown'
            }
    
    def _handle_experience_level(self, user_id: int, callback_data: str) -> Dict:
        """Gère l'étape niveau d'expérience"""
        try:
            if callback_data == 'skip_step':
                self.user_data[user_id]['experience_level'] = 'beginner'
            else:
                level_map = {
                    'exp_beginner': 'beginner',
                    'exp_intermediate': 'intermediate',
                    'exp_advanced': 'advanced'
                }
                self.user_data[user_id]['experience_level'] = level_map.get(callback_data, 'beginner')
            
            # Passer à l'étape suivante
            self.onboarding_states[user_id] = 'risk_profile'
            
            message = """📊 **Étape 2/5: Profil de risque**

Quel est votre profil de risque d'investissement ?

🔒 **Conservateur:**
• Priorité à la sécurité
• Croissance lente mais stable
• 60-70% BTC/ETH, 20-30% stablecoins

⚖️ **Modéré:**
• Équilibre risque/récompense
• Diversification équilibrée
• 50-60% BTC/ETH, 20-30% altcoins

🚀 **Agressif:**
• Recherche de croissance maximale
• Tolérance aux volatilités
• 40-50% altcoins, 30-40% BTC/ETH"""
            
            keyboard = [
                [{"text": "🔒 Conservateur", "callback_data": "risk_conservative"}],
                [{"text": "⚖️ Modéré", "callback_data": "risk_moderate"}],
                [{"text": "🚀 Agressif", "callback_data": "risk_aggressive"}],
                [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur étape expérience: {e}")
            return self._finish_onboarding(user_id)
    
    def _handle_risk_profile(self, user_id: int, callback_data: str) -> Dict:
        """Gère l'étape profil de risque"""
        try:
            if callback_data == 'skip_step':
                self.user_data[user_id]['risk_profile'] = 'moderate'
            else:
                risk_map = {
                    'risk_conservative': 'conservative',
                    'risk_moderate': 'moderate',
                    'risk_aggressive': 'aggressive'
                }
                self.user_data[user_id]['risk_profile'] = risk_map.get(callback_data, 'moderate')
            
            # Passer à l'étape suivante
            self.onboarding_states[user_id] = 'investment_goals'
            
            message = """🎯 **Étape 3/5: Objectifs d'investissement**

Quels sont vos principaux objectifs ? (Sélectionnez plusieurs)

💰 **Objectifs disponibles:**
• **Épargne:** Constituer une épargne
• **Croissance:** Faire croître le capital
• **Revenus:** Générer des revenus passifs
• **Hedge:** Protection contre l'inflation
• **Trading:** Trading actif et spéculation
• **Long terme:** Investissement long terme (5+ ans)"""
            
            keyboard = [
                [{"text": "💰 Épargne", "callback_data": "goal_savings"}],
                [{"text": "📈 Croissance", "callback_data": "goal_growth"}],
                [{"text": "💸 Revenus", "callback_data": "goal_income"}],
                [{"text": "🛡️ Hedge", "callback_data": "goal_hedge"}],
                [{"text": "📊 Trading", "callback_data": "goal_trading"}],
                [{"text": "⏰ Long terme", "callback_data": "goal_longterm"}],
                [{"text": "✅ Terminer", "callback_data": "finish_goals"}],
                [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur étape risque: {e}")
            return self._finish_onboarding(user_id)
    
    def _handle_investment_goals(self, user_id: int, callback_data: str) -> Dict:
        """Gère l'étape objectifs d'investissement"""
        try:
            if callback_data == 'skip_step':
                self.user_data[user_id]['investment_goals'] = ['growth']
            elif callback_data == 'finish_goals':
                # Garder les objectifs sélectionnés
                pass
            else:
                # Ajouter l'objectif sélectionné
                goal_map = {
                    'goal_savings': 'savings',
                    'goal_growth': 'growth',
                    'goal_income': 'income',
                    'goal_hedge': 'hedge',
                    'goal_trading': 'trading',
                    'goal_longterm': 'longterm'
                }
                
                if 'investment_goals' not in self.user_data[user_id]:
                    self.user_data[user_id]['investment_goals'] = []
                
                goal = goal_map.get(callback_data)
                if goal and goal not in self.user_data[user_id]['investment_goals']:
                    self.user_data[user_id]['investment_goals'].append(goal)
                
                # Afficher les objectifs sélectionnés
                selected_goals = self.user_data[user_id]['investment_goals']
                goals_text = ', '.join(selected_goals) if selected_goals else 'Aucun'
                
                message = f"""🎯 **Objectifs sélectionnés:** {goals_text}

Sélectionnez d'autres objectifs ou terminez cette étape."""
                
                keyboard = [
                    [{"text": "💰 Épargne", "callback_data": "goal_savings"}],
                    [{"text": "📈 Croissance", "callback_data": "goal_growth"}],
                    [{"text": "💸 Revenus", "callback_data": "goal_income"}],
                    [{"text": "🛡️ Hedge", "callback_data": "goal_hedge"}],
                    [{"text": "📊 Trading", "callback_data": "goal_trading"}],
                    [{"text": "⏰ Long terme", "callback_data": "goal_longterm"}],
                    [{"text": "✅ Terminer", "callback_data": "finish_goals"}],
                    [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
                ]
                
                return {
                    'message': message,
                    'keyboard': keyboard,
                    'parse_mode': 'Markdown'
                }
            
            # Passer à l'étape suivante
            self.onboarding_states[user_id] = 'investment_amount'
            
            message = """💰 **Étape 4/5: Montant d'investissement**

Quel est votre montant d'investissement typique ?

💡 **Ces informations nous aident à:**
• Adapter les recommandations de taille de position
• Suggérer des stratégies appropriées
• Optimiser la diversification

📊 **Fourchettes disponibles:**
• < 1,000€ - Débutant
• 1,000€ - 10,000€ - Intermédiaire
• 10,000€ - 100,000€ - Confirmé
• > 100,000€ - Professionnel"""
            
            keyboard = [
                [{"text": "💸 < 1,000€", "callback_data": "amount_small"}],
                [{"text": "💰 1,000€ - 10,000€", "callback_data": "amount_medium"}],
                [{"text": "🏦 10,000€ - 100,000€", "callback_data": "amount_large"}],
                [{"text": "💎 > 100,000€", "callback_data": "amount_pro"}],
                [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur étape objectifs: {e}")
            return self._finish_onboarding(user_id)
    
    def _handle_investment_amount(self, user_id: int, callback_data: str) -> Dict:
        """Gère l'étape montant d'investissement"""
        try:
            if callback_data == 'skip_step':
                self.user_data[user_id]['investment_amount'] = 'medium'
            else:
                amount_map = {
                    'amount_small': 'small',
                    'amount_medium': 'medium',
                    'amount_large': 'large',
                    'amount_pro': 'professional'
                }
                self.user_data[user_id]['investment_amount'] = amount_map.get(callback_data, 'medium')
            
            # Passer à l'étape suivante
            self.onboarding_states[user_id] = 'time_horizon'
            
            message = """⏰ **Étape 5/5: Horizon temporel**

Quel est votre horizon d'investissement principal ?

📅 **Horizons disponibles:**
• **Court terme:** < 1 an - Trading actif
• **Moyen terme:** 1-3 ans - Croissance modérée
• **Long terme:** 3-5 ans - Accumulation
• **Très long terme:** 5+ ans - Patrimoine"""
            
            keyboard = [
                [{"text": "📅 Court terme (< 1 an)", "callback_data": "horizon_short"}],
                [{"text": "📊 Moyen terme (1-3 ans)", "callback_data": "horizon_medium"}],
                [{"text": "📈 Long terme (3-5 ans)", "callback_data": "horizon_long"}],
                [{"text": "🏛️ Très long terme (5+ ans)", "callback_data": "horizon_verylong"}],
                [{"text": "⏭️ Passer cette étape", "callback_data": "skip_step"}]
            ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur étape montant: {e}")
            return self._finish_onboarding(user_id)
    
    def _handle_time_horizon(self, user_id: int, callback_data: str) -> Dict:
        """Gère l'étape horizon temporel"""
        try:
            if callback_data == 'skip_step':
                self.user_data[user_id]['time_horizon'] = 'medium'
            else:
                horizon_map = {
                    'horizon_short': 'short',
                    'horizon_medium': 'medium',
                    'horizon_long': 'long',
                    'horizon_verylong': 'very_long'
                }
                self.user_data[user_id]['time_horizon'] = horizon_map.get(callback_data, 'medium')
            
            # Terminer l'onboarding
            return self._finish_onboarding(user_id)
            
        except Exception as e:
            print(f"Erreur étape horizon: {e}")
            return self._finish_onboarding(user_id)
    
    def _finish_onboarding(self, user_id: int) -> Dict:
        """Termine le processus d'onboarding"""
        try:
            # Récupérer les données collectées
            user_data = self.user_data.get(user_id, {})
            
            # Mettre à jour le profil utilisateur
            update_success = self.user_service.update_user_profile(
                telegram_id=user_id,
                experience_level=user_data.get('experience_level', 'beginner'),
                risk_profile=user_data.get('risk_profile', 'moderate'),
                investment_goals=user_data.get('investment_goals', ['growth']),
                preferences={
                    'investment_amount': user_data.get('investment_amount', 'medium'),
                    'time_horizon': user_data.get('time_horizon', 'medium')
                }
            )
            
            # Nettoyer les données temporaires
            if user_id in self.onboarding_states:
                del self.onboarding_states[user_id]
            if user_id in self.user_data:
                del self.user_data[user_id]
            
            if update_success:
                message = """✅ **ONBOARDING TERMINÉ !**

🎉 Félicitations ! Votre profil a été configuré avec succès.

📊 **Votre profil:**
• Expérience: {experience}
• Risque: {risk}
• Objectifs: {goals}
• Montant: {amount}
• Horizon: {horizon}

🤖 **Conseils IA personnalisés:**
Vos recommandations seront maintenant adaptées à votre profil.

💎 **Prochaines étapes:**
• Upgrade Premium pour le suivi wallet
• Configurez vos alertes personnalisées
• Recevez des analyses quotidiennes

🚀 **Prêt à investir intelligemment !**""".format(
                    experience=user_data.get('experience_level', 'beginner').title(),
                    risk=user_data.get('risk_profile', 'moderate').title(),
                    goals=', '.join(user_data.get('investment_goals', ['growth'])),
                    amount=user_data.get('investment_amount', 'medium').title(),
                    horizon=user_data.get('time_horizon', 'medium').title()
                )
                
                keyboard = [
                    [{"text": "💎 Voir abonnements", "callback_data": "subscriptions"}],
                    [{"text": "📊 Mon profil", "callback_data": "my_profile"}],
                    [{"text": "🤖 Conseils IA", "callback_data": "ai_advice"}],
                    [{"text": "🔙 Menu principal", "callback_data": "main_menu"}]
                ]
            else:
                message = """⚠️ **Onboarding partiellement terminé**

Certaines informations n'ont pas pu être sauvegardées, mais vous pouvez continuer à utiliser le bot.

💡 **Vous pouvez modifier votre profil plus tard avec /profile**"""
                
                keyboard = [
                    [{"text": "📊 Mon profil", "callback_data": "my_profile"}],
                    [{"text": "🔙 Menu principal", "callback_data": "main_menu"}]
                ]
            
            return {
                'message': message,
                'keyboard': keyboard,
                'parse_mode': 'Markdown'
            }
            
        except Exception as e:
            print(f"Erreur fin onboarding: {e}")
            return {
                'message': "❌ Erreur lors de la finalisation de l'onboarding. Utilisez /profile pour modifier votre profil.",
                'keyboard': [
                    [{"text": "🔙 Menu principal", "callback_data": "main_menu"}]
                ],
                'parse_mode': 'Markdown'
            }
    
    def is_user_in_onboarding(self, user_id: int) -> bool:
        """Vérifie si un utilisateur est en cours d'onboarding"""
        return user_id in self.onboarding_states
    
    def get_onboarding_state(self, user_id: int) -> Optional[str]:
        """Récupère l'état d'onboarding d'un utilisateur"""
        return self.onboarding_states.get(user_id)

# Instance globale
onboarding_handler = OnboardingHandler() 