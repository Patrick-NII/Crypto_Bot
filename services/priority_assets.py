# modules/priority_assets.py
"""
Module de gestion des 40 actifs prioritaires
20 cryptomonnaies + 20 actions les plus rentables (6-12 mois)
"""

import json
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PriorityAssets:
    def __init__(self):
        # 20 Cryptomonnaies prioritaires
        self.priority_crypto = {
            "BTC": {
                "name": "Bitcoin",
                "symbol": "BTC",
                "category": "Store of Value",
                "priority": 1,
                "risk_level": "Modéré",
                "target_6m": "+15%",
                "target_12m": "+35%",
                "analysis_focus": ["Adoption", "Halving", "Institutional"]
            },
            "ETH": {
                "name": "Ethereum",
                "symbol": "ETH", 
                "category": "Smart Contracts",
                "priority": 2,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["DeFi", "Layer 2", "EIP-1559"]
            },
            "SOL": {
                "name": "Solana",
                "symbol": "SOL",
                "category": "High Performance",
                "priority": 3,
                "risk_level": "Élevé",
                "target_6m": "+30%",
                "target_12m": "+60%",
                "analysis_focus": ["Speed", "Ecosystem", "Competition"]
            },
            "ADA": {
                "name": "Cardano",
                "symbol": "ADA",
                "category": "Academic",
                "priority": 4,
                "risk_level": "Modéré",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["Research", "Governance", "Partnerships"]
            },
            "DOT": {
                "name": "Polkadot",
                "symbol": "DOT",
                "category": "Interoperability",
                "priority": 5,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+45%",
                "analysis_focus": ["Parachains", "Ecosystem", "Governance"]
            },
            "AVAX": {
                "name": "Avalanche",
                "symbol": "AVAX",
                "category": "Layer 1",
                "priority": 6,
                "risk_level": "Élevé",
                "target_6m": "+35%",
                "target_12m": "+70%",
                "analysis_focus": ["Subnets", "DeFi", "Institutional"]
            },
            "MATIC": {
                "name": "Polygon",
                "symbol": "MATIC",
                "category": "Layer 2",
                "priority": 7,
                "risk_level": "Modéré",
                "target_6m": "+25%",
                "target_12m": "+55%",
                "analysis_focus": ["Scaling", "Adoption", "Partnerships"]
            },
            "LINK": {
                "name": "Chainlink",
                "symbol": "LINK",
                "category": "Oracle",
                "priority": 8,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["Oracles", "DeFi", "Enterprise"]
            },
            "UNI": {
                "name": "Uniswap",
                "symbol": "UNI",
                "category": "DEX",
                "priority": 9,
                "risk_level": "Modéré",
                "target_6m": "+30%",
                "target_12m": "+60%",
                "analysis_focus": ["Volume", "Fees", "Governance"]
            },
            "ATOM": {
                "name": "Cosmos",
                "symbol": "ATOM",
                "category": "Interoperability",
                "priority": 10,
                "risk_level": "Modéré",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["IBC", "Ecosystem", "Governance"]
            },
            "FTM": {
                "name": "Fantom",
                "symbol": "FTM",
                "category": "Layer 1",
                "priority": 11,
                "risk_level": "Élevé",
                "target_6m": "+40%",
                "target_12m": "+80%",
                "analysis_focus": ["Speed", "DeFi", "Adoption"]
            },
            "NEAR": {
                "name": "NEAR Protocol",
                "symbol": "NEAR",
                "category": "Layer 1",
                "priority": 12,
                "risk_level": "Élevé",
                "target_6m": "+35%",
                "target_12m": "+70%",
                "analysis_focus": ["Sharding", "Ecosystem", "Partnerships"]
            },
            "ALGO": {
                "name": "Algorand",
                "symbol": "ALGO",
                "category": "Layer 1",
                "priority": 13,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+45%",
                "analysis_focus": ["Consensus", "Enterprise", "DeFi"]
            },
            "VET": {
                "name": "VeChain",
                "symbol": "VET",
                "category": "Enterprise",
                "priority": 14,
                "risk_level": "Modéré",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["Supply Chain", "Partnerships", "Adoption"]
            },
            "THETA": {
                "name": "Theta Network",
                "symbol": "THETA",
                "category": "Video",
                "priority": 15,
                "risk_level": "Élevé",
                "target_6m": "+30%",
                "target_12m": "+65%",
                "analysis_focus": ["Video", "CDN", "Partnerships"]
            },
            "XTZ": {
                "name": "Tezos",
                "symbol": "XTZ",
                "category": "Smart Contracts",
                "priority": 16,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["Governance", "DeFi", "NFTs"]
            },
            "FIL": {
                "name": "Filecoin",
                "symbol": "FIL",
                "category": "Storage",
                "priority": 17,
                "risk_level": "Élevé",
                "target_6m": "+35%",
                "target_12m": "+70%",
                "analysis_focus": ["Storage", "Web3", "Adoption"]
            },
            "ICP": {
                "name": "Internet Computer",
                "symbol": "ICP",
                "category": "Web3",
                "priority": 18,
                "risk_level": "Élevé",
                "target_6m": "+40%",
                "target_12m": "+80%",
                "analysis_focus": ["Web3", "Canisters", "Ecosystem"]
            },
            "HBAR": {
                "name": "Hedera",
                "symbol": "HBAR",
                "category": "Enterprise",
                "priority": 19,
                "risk_level": "Modéré",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["Enterprise", "Governance", "Partnerships"]
            },
            "ONE": {
                "name": "Harmony",
                "symbol": "ONE",
                "category": "Layer 1",
                "priority": 20,
                "risk_level": "Élevé",
                "target_6m": "+30%",
                "target_12m": "+60%",
                "analysis_focus": ["Sharding", "DeFi", "Cross-chain"]
            }
        }
        
        # 20 Actions prioritaires
        self.priority_stocks = {
            "AAPL": {
                "name": "Apple Inc.",
                "symbol": "AAPL",
                "sector": "Technology",
                "priority": 1,
                "risk_level": "Faible",
                "target_6m": "+10%",
                "target_12m": "+20%",
                "analysis_focus": ["iPhone", "Services", "Innovation"]
            },
            "MSFT": {
                "name": "Microsoft Corporation",
                "symbol": "MSFT",
                "sector": "Technology",
                "priority": 2,
                "risk_level": "Faible",
                "target_6m": "+12%",
                "target_12m": "+25%",
                "analysis_focus": ["Azure", "Office", "AI"]
            },
            "GOOGL": {
                "name": "Alphabet Inc.",
                "symbol": "GOOGL",
                "sector": "Technology",
                "priority": 3,
                "risk_level": "Faible",
                "target_6m": "+15%",
                "target_12m": "+30%",
                "analysis_focus": ["Search", "YouTube", "AI"]
            },
            "AMZN": {
                "name": "Amazon.com Inc.",
                "symbol": "AMZN",
                "sector": "Consumer Discretionary",
                "priority": 4,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["E-commerce", "AWS", "Logistics"]
            },
            "TSLA": {
                "name": "Tesla Inc.",
                "symbol": "TSLA",
                "sector": "Automotive",
                "priority": 5,
                "risk_level": "Élevé",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["EV", "Autonomous", "Energy"]
            },
            "NVDA": {
                "name": "NVIDIA Corporation",
                "symbol": "NVDA",
                "sector": "Technology",
                "priority": 6,
                "risk_level": "Modéré",
                "target_6m": "+30%",
                "target_12m": "+60%",
                "analysis_focus": ["AI", "Gaming", "Data Centers"]
            },
            "META": {
                "name": "Meta Platforms Inc.",
                "symbol": "META",
                "sector": "Technology",
                "priority": 7,
                "risk_level": "Modéré",
                "target_6m": "+18%",
                "target_12m": "+35%",
                "analysis_focus": ["Social Media", "VR", "AI"]
            },
            "BRK.B": {
                "name": "Berkshire Hathaway Inc.",
                "symbol": "BRK.B",
                "sector": "Financial",
                "priority": 8,
                "risk_level": "Faible",
                "target_6m": "+8%",
                "target_12m": "+15%",
                "analysis_focus": ["Diversified", "Buffett", "Stability"]
            },
            "JPM": {
                "name": "JPMorgan Chase & Co.",
                "symbol": "JPM",
                "sector": "Financial",
                "priority": 9,
                "risk_level": "Modéré",
                "target_6m": "+12%",
                "target_12m": "+25%",
                "analysis_focus": ["Banking", "Trading", "Digital"]
            },
            "JNJ": {
                "name": "Johnson & Johnson",
                "symbol": "JNJ",
                "sector": "Healthcare",
                "priority": 10,
                "risk_level": "Faible",
                "target_6m": "+8%",
                "target_12m": "+18%",
                "analysis_focus": ["Pharma", "Medical Devices", "Consumer"]
            },
            "PG": {
                "name": "Procter & Gamble Co.",
                "symbol": "PG",
                "sector": "Consumer Staples",
                "priority": 11,
                "risk_level": "Faible",
                "target_6m": "+6%",
                "target_12m": "+12%",
                "analysis_focus": ["Consumer Goods", "Stability", "Dividend"]
            },
            "V": {
                "name": "Visa Inc.",
                "symbol": "V",
                "sector": "Financial",
                "priority": 12,
                "risk_level": "Modéré",
                "target_6m": "+15%",
                "target_12m": "+30%",
                "analysis_focus": ["Payments", "Digital", "Global"]
            },
            "HD": {
                "name": "Home Depot Inc.",
                "symbol": "HD",
                "sector": "Consumer Discretionary",
                "priority": 13,
                "risk_level": "Modéré",
                "target_6m": "+10%",
                "target_12m": "+20%",
                "analysis_focus": ["Retail", "Home Improvement", "E-commerce"]
            },
            "MA": {
                "name": "Mastercard Inc.",
                "symbol": "MA",
                "sector": "Financial",
                "priority": 14,
                "risk_level": "Modéré",
                "target_6m": "+15%",
                "target_12m": "+30%",
                "analysis_focus": ["Payments", "Digital", "Innovation"]
            },
            "UNH": {
                "name": "UnitedHealth Group Inc.",
                "symbol": "UNH",
                "sector": "Healthcare",
                "priority": 15,
                "risk_level": "Modéré",
                "target_6m": "+12%",
                "target_12m": "+25%",
                "analysis_focus": ["Insurance", "Healthcare", "Technology"]
            },
            "DIS": {
                "name": "Walt Disney Co.",
                "symbol": "DIS",
                "sector": "Communication Services",
                "priority": 16,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["Streaming", "Parks", "Content"]
            },
            "ADBE": {
                "name": "Adobe Inc.",
                "symbol": "ADBE",
                "sector": "Technology",
                "priority": 17,
                "risk_level": "Modéré",
                "target_6m": "+18%",
                "target_12m": "+35%",
                "analysis_focus": ["Creative Software", "Cloud", "AI"]
            },
            "CRM": {
                "name": "Salesforce Inc.",
                "symbol": "CRM",
                "sector": "Technology",
                "priority": 18,
                "risk_level": "Modéré",
                "target_6m": "+20%",
                "target_12m": "+40%",
                "analysis_focus": ["CRM", "Cloud", "AI"]
            },
            "NFLX": {
                "name": "Netflix Inc.",
                "symbol": "NFLX",
                "sector": "Communication Services",
                "priority": 19,
                "risk_level": "Élevé",
                "target_6m": "+25%",
                "target_12m": "+50%",
                "analysis_focus": ["Streaming", "Content", "International"]
            },
            "PYPL": {
                "name": "PayPal Holdings Inc.",
                "symbol": "PYPL",
                "sector": "Financial",
                "priority": 20,
                "risk_level": "Modéré",
                "target_6m": "+18%",
                "target_12m": "+35%",
                "analysis_focus": ["Digital Payments", "E-commerce", "Innovation"]
            }
        }

    def get_crypto_list(self) -> List[str]:
        """Retourne la liste des cryptos prioritaires"""
        return list(self.priority_crypto.keys())
    
    def get_stocks_list(self) -> List[str]:
        """Retourne la liste des actions prioritaires"""
        return list(self.priority_stocks.keys())
    
    def get_all_assets(self) -> Dict[str, Dict]:
        """Retourne tous les actifs prioritaires"""
        return {
            "crypto": self.priority_crypto,
            "stocks": self.priority_stocks
        }
    
    def get_asset_info(self, symbol: str) -> Optional[Dict]:
        """Retourne les informations d'un actif"""
        symbol = symbol.upper()
        
        if symbol in self.priority_crypto:
            return self.priority_crypto[symbol]
        elif symbol in self.priority_stocks:
            return self.priority_stocks[symbol]
        else:
            return None
    
    def is_priority_asset(self, symbol: str) -> bool:
        """Vérifie si un actif fait partie des prioritaires"""
        symbol = symbol.upper()
        return symbol in self.priority_crypto or symbol in self.priority_stocks
    
    def get_analysis_focus(self, symbol: str) -> List[str]:
        """Retourne les points d'analyse pour un actif"""
        asset_info = self.get_asset_info(symbol)
        if asset_info:
            return asset_info.get("analysis_focus", [])
        return []
    
    def get_risk_level(self, symbol: str) -> str:
        """Retourne le niveau de risque d'un actif"""
        asset_info = self.get_asset_info(symbol)
        if asset_info:
            return asset_info.get("risk_level", "Inconnu")
        return "Inconnu"
    
    def get_targets(self, symbol: str) -> Dict[str, str]:
        """Retourne les objectifs de prix d'un actif"""
        asset_info = self.get_asset_info(symbol)
        if asset_info:
            return {
                "6m": asset_info.get("target_6m", "N/A"),
                "12m": asset_info.get("target_12m", "N/A")
            }
        return {"6m": "N/A", "12m": "N/A"}
    
    def get_top_crypto(self, limit: int = 10) -> List[Dict]:
        """Retourne les top cryptos par priorité"""
        sorted_crypto = sorted(
            self.priority_crypto.items(),
            key=lambda x: x[1]["priority"]
        )
        return [{"symbol": k, **v} for k, v in sorted_crypto[:limit]]
    
    def get_top_stocks(self, limit: int = 10) -> List[Dict]:
        """Retourne les top actions par priorité"""
        sorted_stocks = sorted(
            self.priority_stocks.items(),
            key=lambda x: x[1]["priority"]
        )
        return [{"symbol": k, **v} for k, v in sorted_stocks[:limit]]
    
    def get_assets_by_risk(self, risk_level: str) -> Dict[str, List[str]]:
        """Retourne les actifs par niveau de risque"""
        crypto_by_risk = [
            symbol for symbol, info in self.priority_crypto.items()
            if info["risk_level"] == risk_level
        ]
        stocks_by_risk = [
            symbol for symbol, info in self.priority_stocks.items()
            if info["risk_level"] == risk_level
        ]
        
        return {
            "crypto": crypto_by_risk,
            "stocks": stocks_by_risk
        }
    
    def get_portfolio_recommendation(self, risk_profile: str) -> Dict:
        """Retourne des recommandations de portefeuille selon le profil de risque"""
        if risk_profile == "conservateur":
            crypto_assets = self.get_assets_by_risk("Faible")["crypto"] + self.get_assets_by_risk("Modéré")["crypto"][:5]
            stock_assets = self.get_assets_by_risk("Faible")["stocks"] + self.get_assets_by_risk("Modéré")["stocks"][:10]
        elif risk_profile == "modéré":
            crypto_assets = self.get_assets_by_risk("Modéré")["crypto"] + self.get_assets_by_risk("Élevé")["crypto"][:5]
            stock_assets = self.get_assets_by_risk("Modéré")["stocks"] + self.get_assets_by_risk("Faible")["stocks"][:5]
        else:  # agressif
            crypto_assets = self.get_assets_by_risk("Élevé")["crypto"] + self.get_assets_by_risk("Modéré")["crypto"][:10]
            stock_assets = self.get_assets_by_risk("Élevé")["stocks"] + self.get_assets_by_risk("Modéré")["stocks"][:10]
        
        return {
            "crypto": crypto_assets[:10],  # Max 10 crypto
            "stocks": stock_assets[:10],   # Max 10 actions
            "risk_profile": risk_profile
        }

# Instance globale
priority_assets = PriorityAssets() 