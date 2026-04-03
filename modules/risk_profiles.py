# modules/risk_profiles.py
import json
import random
from datetime import datetime

class RiskProfiles:
    def __init__(self):
        self.profiles = {
            "conservateur": {
                "name": "Conservateur",
                "emoji": "🛡️",
                "description": "Préserve le capital, croissance lente mais sûre",
                "allocation": {
                    "crypto": "5-15%",
                    "actions": "30-50%",
                    "obligations": "40-60%",
                    "liquidites": "5-10%"
                },
                "risk_level": "Faible",
                "expected_return": "3-6%",
                "max_drawdown": "-10%",
                "recommendations": [
                    "Privilégiez les actions de grandes entreprises (blue chips)",
                    "Investissez dans des ETF diversifiés",
                    "Gardez une réserve de liquidités importante",
                    "Évitez les cryptomonnaies volatiles",
                    "Considérez l'immobilier locatif"
                ],
                "warnings": [
                    "⚠️ Évitez les investissements spéculatifs",
                    "⚠️ Ne mettez pas plus de 5% en crypto",
                    "⚠️ Privilégiez la stabilité à la performance"
                ]
            },
            "modéré": {
                "name": "Modéré",
                "emoji": "⚖️",
                "description": "Équilibre entre croissance et sécurité",
                "allocation": {
                    "crypto": "10-25%",
                    "actions": "50-70%",
                    "obligations": "20-40%",
                    "liquidites": "5-15%"
                },
                "risk_level": "Moyen",
                "expected_return": "6-10%",
                "max_drawdown": "-20%",
                "recommendations": [
                    "Diversifiez entre actions et crypto",
                    "Incluez des ETF sectoriels",
                    "Considérez le DCA pour les cryptos",
                    "Gardez une réserve de 3-6 mois",
                    "Surveillez régulièrement vos positions"
                ],
                "warnings": [
                    "⚠️ Limitez l'exposition crypto à 25% maximum",
                    "⚠️ Diversifiez géographiquement",
                    "⚠️ Rééquilibrez trimestriellement"
                ]
            },
            "agressif": {
                "name": "Agressif",
                "emoji": "🚀",
                "description": "Maximise la croissance, accepte la volatilité",
                "allocation": {
                    "crypto": "30-50%",
                    "actions": "40-60%",
                    "obligations": "0-20%",
                    "liquidites": "5-10%"
                },
                "risk_level": "Élevé",
                "expected_return": "10-20%",
                "max_drawdown": "-40%",
                "recommendations": [
                    "Privilégiez les cryptomonnaies prometteuses",
                    "Investissez dans des actions de croissance",
                    "Considérez le trading actif",
                    "Surveillez les tendances de marché",
                    "Soyez prêt à la volatilité"
                ],
                "warnings": [
                    "⚠️ Risque de pertes importantes",
                    "⚠️ Surveillez quotidiennement vos positions",
                    "⚠️ Ayez un plan de sortie",
                    "⚠️ Ne mettez pas tout votre capital"
                ]
            }
        }

    def get_profile_info(self, profile_name):
        """Retourne les informations d'un profil de risque"""
        profile_name = profile_name.lower().strip()
        
        for key, profile in self.profiles.items():
            if key in profile_name or profile_name in key:
                return profile
        
        return None

    def analyze_current_portfolio(self, crypto_value, pea_value, total_value):
        """Analyse le portefeuille actuel et suggère un profil"""
        crypto_percent = (crypto_value / total_value) * 100 if total_value > 0 else 0
        pea_percent = (pea_value / total_value) * 100 if total_value > 0 else 0
        
        # Déterminer le profil basé sur l'allocation actuelle
        if crypto_percent > 30:
            current_profile = "agressif"
        elif crypto_percent > 15:
            current_profile = "modéré"
        else:
            current_profile = "conservateur"
        
        profile_info = self.profiles[current_profile]
        
        analysis = f"""📊 **Analyse de Votre Profil de Risque**

{profile_info['emoji']} **Profil détecté : {profile_info['name']}**
📈 **Niveau de risque : {profile_info['risk_level']}**
💰 **Rendement attendu : {profile_info['expected_return']}**
📉 **Drawdown max : {profile_info['max_drawdown']}**

📊 **Votre allocation actuelle :**
• Crypto : {crypto_percent:.1f}%
• Actions PEA : {pea_percent:.1f}%

💡 **Recommandations :**
"""
        
        for rec in profile_info['recommendations'][:3]:  # Limiter à 3 recommandations
            analysis += f"• {rec}\n"
        
        analysis += f"\n⚠️ **Attention :**\n"
        for warning in profile_info['warnings'][:2]:  # Limiter à 2 warnings
            analysis += f"{warning}\n"
        
        return analysis

    def get_allocation_suggestion(self, profile_name, total_amount):
        """Suggère une allocation pour un profil donné"""
        profile = self.get_profile_info(profile_name)
        if not profile:
            return "❌ Profil non reconnu"
        
        allocation = profile['allocation']
        
        suggestion = f"""💰 **Suggestion d'Allocation - Profil {profile['name']}**

📊 **Répartition recommandée :**
• Crypto : {allocation['crypto']} ({(total_amount * 0.15):,.0f}€)
• Actions : {allocation['actions']} ({(total_amount * 0.6):,.0f}€)
• Obligations : {allocation['obligations']} ({(total_amount * 0.2):,.0f}€)
• Liquidités : {allocation['liquidites']} ({(total_amount * 0.05):,.0f}€)

💡 **Stratégie :**
{profile['description']}

⚠️ **Risque :** {profile['risk_level']}
📈 **Rendement attendu :** {profile['expected_return']}"""
        
        return suggestion

    def get_profile_comparison(self):
        """Compare les 3 profils de risque"""
        comparison = "📊 **Comparaison des Profils de Risque**\n\n"
        
        for key, profile in self.profiles.items():
            comparison += f"{profile['emoji']} **{profile['name']}**\n"
            comparison += f"📈 Risque : {profile['risk_level']}\n"
            comparison += f"💰 Rendement : {profile['expected_return']}\n"
            comparison += f"📉 Drawdown max : {profile['max_drawdown']}\n"
            comparison += f"💡 {profile['description']}\n\n"
        
        comparison += "💡 *Choisissez selon votre tolérance au risque et vos objectifs*"
        
        return comparison

    def get_risk_advice(self, current_crypto_percent):
        """Donne des conseils basés sur l'exposition crypto actuelle"""
        if current_crypto_percent > 40:
            advice = f"""⚠️ **Attention - Exposition Crypto Élevée ({current_crypto_percent:.1f}%)**

🚨 **Risques :**
• Volatilité extrême
• Perte potentielle importante
• Stress émotionnel

💡 **Recommandations :**
• Réduisez progressivement l'exposition
• Diversifiez vers des actions stables
• Gardez une réserve de liquidités
• Considérez le profil modéré"""
        
        elif current_crypto_percent > 20:
            advice = f"""⚖️ **Exposition Crypto Modérée ({current_crypto_percent:.1f}%)**

✅ **Équilibre correct :**
• Bonne diversification
• Potentiel de croissance
• Risque maîtrisé

💡 **Optimisations :**
• Surveillez les tendances
• Rééquilibrez si nécessaire
• Maintenez la diversification"""
        
        else:
            advice = f"""🛡️ **Exposition Crypto Faible ({current_crypto_percent:.1f}%)**

✅ **Profil conservateur :**
• Risque limité
• Stabilité du capital
• Croissance lente mais sûre

💡 **Opportunités :**
• Considérez une légère augmentation crypto
• Diversifiez géographiquement
• Optimisez les frais"""
        
        return advice 