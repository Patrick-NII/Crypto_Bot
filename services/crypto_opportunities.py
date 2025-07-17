# modules/crypto_opportunities.py
"""
Module d'analyse des opportunités crypto
Méthodes d'analyse financière avancées pour identifier les crypto à fort potentiel
"""

import os
import json
import requests
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from modules.sources_manager import sources_manager
from modules.technical_analysis import technical_analysis

class CryptoOpportunitiesAnalyzer:
    def __init__(self):
        self.api_key = os.getenv('COINGECKO_API_KEY', '')  # Optionnel
        self.base_url = "https://api.coingecko.com/api/v3"
        self.analysis_cache = {}
        self.cache_duration = 3600  # 1 heure
        
    def get_market_data(self, crypto_id: str) -> Dict:
        """Récupère les données de marché d'une crypto"""
        try:
            url = f"{self.base_url}/coins/{crypto_id}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'true',
                'sparkline': 'false'
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return {"error": f"API error: {response.status_code}"}
                
        except Exception as e:
            return {"error": f"Request error: {str(e)}"}
    
    def analyze_crypto_fundamentals(self, crypto_data: Dict) -> Dict:
        """Analyse fondamentale d'une crypto"""
        try:
            market_data = crypto_data.get('market_data', {})
            community_data = crypto_data.get('community_data', {})
            developer_data = crypto_data.get('developer_data', {})
            
            # Métriques de marché
            market_cap = market_data.get('market_cap', {}).get('usd', 0)
            volume_24h = market_data.get('total_volume', {}).get('usd', 0)
            price_change_24h = market_data.get('price_change_percentage_24h', 0)
            price_change_7d = market_data.get('price_change_percentage_7d', 0)
            price_change_30d = market_data.get('price_change_percentage_30d', 0)
            
            # Métriques communautaires
            reddit_subscribers = community_data.get('reddit_subscribers', 0)
            twitter_followers = community_data.get('twitter_followers', 0)
            telegram_channel_user_count = community_data.get('telegram_channel_user_count', 0)
            
            # Métriques développeur
            github_commits = developer_data.get('commit_count_4_weeks', 0)
            github_stars = developer_data.get('stars', 0)
            github_forks = developer_data.get('forks', 0)
            
            # Calcul des scores
            market_score = self.calculate_market_score(market_cap, volume_24h, price_change_24h, price_change_7d, price_change_30d)
            community_score = self.calculate_community_score(reddit_subscribers, twitter_followers, telegram_channel_user_count)
            developer_score = self.calculate_developer_score(github_commits, github_stars, github_forks)
            
            # Score global
            total_score = (market_score * 0.4 + community_score * 0.3 + developer_score * 0.3)
            
            return {
                "market_metrics": {
                    "market_cap": market_cap,
                    "volume_24h": volume_24h,
                    "price_change_24h": price_change_24h,
                    "price_change_7d": price_change_7d,
                    "price_change_30d": price_change_30d
                },
                "community_metrics": {
                    "reddit_subscribers": reddit_subscribers,
                    "twitter_followers": twitter_followers,
                    "telegram_users": telegram_channel_user_count
                },
                "developer_metrics": {
                    "github_commits_4w": github_commits,
                    "github_stars": github_stars,
                    "github_forks": github_forks
                },
                "scores": {
                    "market_score": market_score,
                    "community_score": community_score,
                    "developer_score": developer_score,
                    "total_score": total_score
                },
                "confidence_level": self.calculate_confidence_level(total_score, market_cap, volume_24h)
            }
            
        except Exception as e:
            return {"error": f"Erreur analyse fondamentale: {str(e)}"}
    
    def calculate_market_score(self, market_cap: float, volume_24h: float, 
                             change_24h: float, change_7d: float, change_30d: float) -> float:
        """Calcule le score de marché (0-100)"""
        score = 0
        
        # Score basé sur la capitalisation (éviter les micro-caps)
        if market_cap > 1000000000:  # > 1B
            score += 25
        elif market_cap > 100000000:  # > 100M
            score += 20
        elif market_cap > 10000000:  # > 10M
            score += 15
        elif market_cap > 1000000:  # > 1M
            score += 10
        
        # Score basé sur le volume (liquidité)
        volume_ratio = volume_24h / market_cap if market_cap > 0 else 0
        if volume_ratio > 0.1:  # > 10%
            score += 25
        elif volume_ratio > 0.05:  # > 5%
            score += 20
        elif volume_ratio > 0.02:  # > 2%
            score += 15
        
        # Score basé sur la performance
        if change_24h > 0:
            score += 10
        if change_7d > 0:
            score += 10
        if change_30d > 0:
            score += 10
        
        # Bonus pour la stabilité
        if abs(change_24h) < 10:  # Volatilité modérée
            score += 10
        
        return min(score, 100)
    
    def calculate_community_score(self, reddit: int, twitter: int, telegram: int) -> float:
        """Calcule le score communautaire (0-100)"""
        score = 0
        
        # Score basé sur la taille de la communauté
        total_followers = reddit + twitter + telegram
        
        if total_followers > 1000000:  # > 1M
            score += 40
        elif total_followers > 100000:  # > 100K
            score += 30
        elif total_followers > 10000:  # > 10K
            score += 20
        elif total_followers > 1000:  # > 1K
            score += 10
        
        # Score basé sur la diversité des plateformes
        platforms = 0
        if reddit > 0:
            platforms += 1
        if twitter > 0:
            platforms += 1
        if telegram > 0:
            platforms += 1
        
        score += platforms * 20
        
        return min(score, 100)
    
    def calculate_developer_score(self, commits: int, stars: int, forks: int) -> float:
        """Calcule le score développeur (0-100)"""
        score = 0
        
        # Score basé sur l'activité de développement
        if commits > 100:
            score += 40
        elif commits > 50:
            score += 30
        elif commits > 20:
            score += 20
        elif commits > 10:
            score += 10
        
        # Score basé sur la popularité du code
        if stars > 1000:
            score += 30
        elif stars > 500:
            score += 20
        elif stars > 100:
            score += 10
        
        # Score basé sur les forks (adoption)
        if forks > 500:
            score += 30
        elif forks > 100:
            score += 20
        elif forks > 50:
            score += 10
        
        return min(score, 100)
    
    def calculate_confidence_level(self, total_score: float, market_cap: float, volume_24h: float) -> float:
        """Calcule le niveau de confiance (0-100)"""
        confidence = total_score * 0.6  # 60% basé sur le score total
        
        # Bonus pour la liquidité
        volume_ratio = volume_24h / market_cap if market_cap > 0 else 0
        if volume_ratio > 0.05:
            confidence += 20
        elif volume_ratio > 0.02:
            confidence += 10
        
        # Bonus pour la taille de marché (éviter les micro-caps)
        if market_cap > 10000000:  # > 10M
            confidence += 20
        elif market_cap > 1000000:  # > 1M
            confidence += 10
        
        return min(confidence, 100)
    
    def get_top_opportunities(self, min_confidence: float = 80.0) -> List[Dict]:
        """Identifie les top 5 crypto avec le plus fort potentiel"""
        try:
            # Liste de crypto prometteuses à analyser
            crypto_list = [
                "bitcoin", "ethereum", "binancecoin", "solana", "cardano",
                "polkadot", "chainlink", "polygon", "avalanche-2", "cosmos",
                "uniswap", "litecoin", "stellar", "algorand", "vechain",
                "filecoin", "tezos", "monero", "dash", "zcash",
                "decred", "nano", "icon", "ontology", "qtum",
                "waves", "stratis", "ark", "lisk", "komodo"
            ]
            
            opportunities = []
            
            for crypto_id in crypto_list:
                # Vérifier le cache
                cache_key = f"opportunity_{crypto_id}"
                if cache_key in self.analysis_cache:
                    cached_data = self.analysis_cache[cache_key]
                    if time.time() - cached_data["timestamp"] < self.cache_duration:
                        if cached_data["confidence_level"] >= min_confidence:
                            opportunities.append(cached_data["data"])
                        continue
                
                # Analyser la crypto
                crypto_data = self.get_market_data(crypto_id)
                if "error" in crypto_data:
                    continue
                
                analysis = self.analyze_crypto_fundamentals(crypto_data)
                if "error" in analysis:
                    continue
                
                # Ajouter les informations de base
                analysis["crypto_info"] = {
                    "id": crypto_id,
                    "name": crypto_data.get("name", crypto_id),
                    "symbol": crypto_data.get("symbol", crypto_id.upper()),
                    "current_price": crypto_data.get("market_data", {}).get("current_price", {}).get("usd", 0)
                }
                
                # Mettre en cache
                self.analysis_cache[cache_key] = {
                    "data": analysis,
                    "timestamp": time.time(),
                    "confidence_level": analysis.get("confidence_level", 0)
                }
                
                # Ajouter si le niveau de confiance est suffisant
                if analysis.get("confidence_level", 0) >= min_confidence:
                    opportunities.append(analysis)
                
                # Pause pour éviter de surcharger l'API
                time.sleep(0.5)
            
            # Trier par score total décroissant
            opportunities.sort(key=lambda x: x.get("scores", {}).get("total_score", 0), reverse=True)
            
            return opportunities[:5]  # Top 5
            
        except Exception as e:
            return [{"error": f"Erreur analyse opportunités: {str(e)}"}]
    
    def generate_opportunities_report(self, opportunities: List[Dict]) -> str:
        """Génère un rapport détaillé des opportunités"""
        if not opportunities:
            return "❌ Aucune opportunité trouvée avec le niveau de confiance requis."
        
        report = f"""🚀 **TOP 5 OPPORTUNITÉS CRYPTO - ANALYSE FINANCIÈRE**

📊 **Méthodologie :** Analyse fondamentale avancée combinant métriques de marché, communautaire et développement
🎯 **Niveau de confiance minimum :** 80%
📅 **Date d'analyse :** {datetime.now().strftime('%d/%m/%Y %H:%M')}

"""
        
        for i, opp in enumerate(opportunities, 1):
            if "error" in opp:
                continue
                
            crypto_info = opp.get("crypto_info", {})
            scores = opp.get("scores", {})
            market_metrics = opp.get("market_metrics", {})
            
            report += f"""**{i}. {crypto_info.get('name', 'N/A')} ({crypto_info.get('symbol', 'N/A')})**
💰 **Prix actuel :** ${crypto_info.get('current_price', 0):,.4f}
📈 **Score global :** {scores.get('total_score', 0):.1f}/100
🎯 **Niveau de confiance :** {opp.get('confidence_level', 0):.1f}%

📊 **Métriques de marché :**
• Capitalisation : ${market_metrics.get('market_cap', 0):,.0f}
• Volume 24h : ${market_metrics.get('volume_24h', 0):,.0f}
• Variation 24h : {market_metrics.get('price_change_24h', 0):+.2f}%
• Variation 7j : {market_metrics.get('price_change_7d', 0):+.2f}%

🏆 **Scores détaillés :**
• Marché : {scores.get('market_score', 0):.1f}/100
• Communauté : {scores.get('community_score', 0):.1f}/100
• Développement : {scores.get('developer_score', 0):.1f}/100

"""
        
        report += f"""
💡 **Recommandations :**
• Diversifiez sur plusieurs crypto de la liste
• Surveillez les métriques de développement
• Analysez la concurrence dans chaque secteur
• Maintenez une stratégie de DCA

⚠️ **Avertissement :** Cette analyse ne constitue pas un conseil financier. Faites vos propres recherches.

🔍 **Sources utilisées :** CoinGecko API, analyse technique, métriques communautaires
"""
        
        return report

# Instance globale
crypto_opportunities = CryptoOpportunitiesAnalyzer() 