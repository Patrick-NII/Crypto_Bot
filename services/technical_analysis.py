# modules/technical_analysis.py
"""
Module d'analyse technique basique
RSI, MACD, moyennes mobiles, support/résistance, patterns
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import requests
import json

class TechnicalAnalysis:
    def __init__(self):
        self.indicators = {
            "rsi": {"period": 14, "overbought": 70, "oversold": 30},
            "macd": {"fast": 12, "slow": 26, "signal": 9},
            "sma": {"short": 20, "medium": 50, "long": 200},
            "ema": {"short": 12, "medium": 26, "long": 50}
        }
        
    def get_asset_data(self, symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Récupère les données historiques d'un actif"""
        try:
            if symbol in ["BTC", "ETH", "SOL", "ADA", "DOT", "AVAX", "MATIC", "LINK", "UNI", "ATOM"]:
                # Pour les cryptos, utiliser un endpoint crypto
                return self.get_crypto_data(symbol, period)
            else:
                # Pour les actions, utiliser yfinance
                ticker = yf.Ticker(symbol)
                data = ticker.history(period=period)
                return data if not data.empty else None
        except Exception as e:
            print(f"Erreur lors de la récupération des données pour {symbol}: {e}")
            return None
    
    def get_crypto_data(self, symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
        """Récupère les données crypto via API"""
        try:
            # Simulation pour l'instant - à remplacer par une vraie API crypto
            days = 180 if period == "6mo" else 365
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            # Générer des données simulées
            dates = pd.date_range(start=start_date, end=end_date, freq='D')
            np.random.seed(hash(symbol) % 1000)  # Pour la reproductibilité
            
            # Prix de base selon le symbole
            base_prices = {
                "BTC": 45000, "ETH": 3000, "SOL": 100, "ADA": 0.5,
                "DOT": 7, "AVAX": 25, "MATIC": 0.8, "LINK": 15,
                "UNI": 8, "ATOM": 10
            }
            
            base_price = base_prices.get(symbol, 100)
            
            # Générer des prix avec tendance et volatilité
            returns = np.random.normal(0.001, 0.03, len(dates))  # 0.1% daily return, 3% volatility
            prices = [base_price]
            
            for ret in returns[1:]:
                new_price = prices[-1] * (1 + ret)
                prices.append(max(new_price, base_price * 0.5))  # Floor à 50% du prix de base
            
            # Créer le DataFrame
            data = pd.DataFrame({
                'Open': prices,
                'High': [p * (1 + abs(np.random.normal(0, 0.02))) for p in prices],
                'Low': [p * (1 - abs(np.random.normal(0, 0.02))) for p in prices],
                'Close': prices,
                'Volume': np.random.randint(1000000, 10000000, len(dates))
            }, index=dates)
            
            return data
            
        except Exception as e:
            print(f"Erreur lors de la récupération des données crypto pour {symbol}: {e}")
            return None
    
    def calculate_rsi(self, data: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calcule le RSI (Relative Strength Index)"""
        try:
            delta = data['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi
        except Exception as e:
            print(f"Erreur calcul RSI: {e}")
            return pd.Series([np.nan] * len(data))
    
    def calculate_macd(self, data: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Calcule le MACD (Moving Average Convergence Divergence)"""
        try:
            ema_fast = data['Close'].ewm(span=fast).mean()
            ema_slow = data['Close'].ewm(span=slow).mean()
            macd_line = ema_fast - ema_slow
            signal_line = macd_line.ewm(span=signal).mean()
            histogram = macd_line - signal_line
            
            return {
                'macd': macd_line,
                'signal': signal_line,
                'histogram': histogram
            }
        except Exception as e:
            print(f"Erreur calcul MACD: {e}")
            return {
                'macd': pd.Series([np.nan] * len(data)),
                'signal': pd.Series([np.nan] * len(data)),
                'histogram': pd.Series([np.nan] * len(data))
            }
    
    def calculate_moving_averages(self, data: pd.DataFrame) -> Dict[str, pd.Series]:
        """Calcule les moyennes mobiles"""
        try:
            return {
                'sma_20': data['Close'].rolling(window=20).mean(),
                'sma_50': data['Close'].rolling(window=50).mean(),
                'sma_200': data['Close'].rolling(window=200).mean(),
                'ema_12': data['Close'].ewm(span=12).mean(),
                'ema_26': data['Close'].ewm(span=26).mean()
            }
        except Exception as e:
            print(f"Erreur calcul moyennes mobiles: {e}")
            return {
                'sma_20': pd.Series([np.nan] * len(data)),
                'sma_50': pd.Series([np.nan] * len(data)),
                'sma_200': pd.Series([np.nan] * len(data)),
                'ema_12': pd.Series([np.nan] * len(data)),
                'ema_26': pd.Series([np.nan] * len(data))
            }
    
    def find_support_resistance(self, data: pd.DataFrame, window: int = 20) -> Dict[str, float]:
        """Trouve les niveaux de support et résistance"""
        try:
            highs = data['High'].rolling(window=window, center=True).max()
            lows = data['Low'].rolling(window=window, center=True).min()
            
            # Trouver les pics et creux
            resistance_levels = []
            support_levels = []
            
            for i in range(window, len(data) - window):
                if data['High'].iloc[i] == highs.iloc[i]:
                    resistance_levels.append(data['High'].iloc[i])
                if data['Low'].iloc[i] == lows.iloc[i]:
                    support_levels.append(data['Low'].iloc[i])
            
            current_price = data['Close'].iloc[-1]
            
            # Trouver les niveaux les plus proches
            resistance = min([r for r in resistance_levels if r > current_price], default=current_price * 1.1)
            support = max([s for s in support_levels if s < current_price], default=current_price * 0.9)
            
            return {
                'resistance': resistance,
                'support': support,
                'current_price': current_price
            }
        except Exception as e:
            print(f"Erreur calcul support/résistance: {e}")
            current_price = data['Close'].iloc[-1] if not data.empty else 100
            return {
                'resistance': current_price * 1.1,
                'support': current_price * 0.9,
                'current_price': current_price
            }
    
    def detect_patterns(self, data: pd.DataFrame) -> Dict[str, bool]:
        """Détecte les patterns de base"""
        try:
            patterns = {}
            
            # Double top/bottom
            highs = data['High'].tail(20)
            lows = data['Low'].tail(20)
            
            # Vérifier double top
            if len(highs) >= 10:
                peak1 = highs.iloc[:10].max()
                peak2 = highs.iloc[10:].max()
                if abs(peak1 - peak2) / peak1 < 0.02:  # 2% de tolérance
                    patterns['double_top'] = True
                else:
                    patterns['double_top'] = False
            
            # Vérifier double bottom
            if len(lows) >= 10:
                trough1 = lows.iloc[:10].min()
                trough2 = lows.iloc[10:].min()
                if abs(trough1 - trough2) / trough1 < 0.02:
                    patterns['double_bottom'] = True
                else:
                    patterns['double_bottom'] = False
            
            # Tendance
            sma_20 = data['Close'].rolling(window=20).mean()
            sma_50 = data['Close'].rolling(window=50).mean()
            
            if len(sma_20) > 0 and len(sma_50) > 0:
                current_20 = sma_20.iloc[-1]
                current_50 = sma_50.iloc[-1]
                prev_20 = sma_20.iloc[-5] if len(sma_20) >= 5 else current_20
                prev_50 = sma_50.iloc[-5] if len(sma_50) >= 5 else current_50
                
                patterns['uptrend'] = current_20 > current_50 and current_20 > prev_20
                patterns['downtrend'] = current_20 < current_50 and current_20 < prev_20
            
            return patterns
            
        except Exception as e:
            print(f"Erreur détection patterns: {e}")
            return {
                'double_top': False,
                'double_bottom': False,
                'uptrend': False,
                'downtrend': False
            }
    
    def get_technical_signals(self, symbol: str) -> Dict:
        """Génère les signaux techniques pour un actif"""
        try:
            data = self.get_asset_data(symbol)
            if data is None or data.empty:
                return {"error": f"Impossible de récupérer les données pour {symbol}"}
            
            # Calculer les indicateurs
            rsi = self.calculate_rsi(data)
            macd_data = self.calculate_macd(data)
            ma_data = self.calculate_moving_averages(data)
            sr_data = self.find_support_resistance(data)
            patterns = self.detect_patterns(data)
            
            current_price = data['Close'].iloc[-1]
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            
            # Générer les signaux
            signals = {
                "symbol": symbol,
                "current_price": current_price,
                "price_change_1d": ((current_price - data['Close'].iloc[-2]) / data['Close'].iloc[-2] * 100) if len(data) > 1 else 0,
                "price_change_7d": ((current_price - data['Close'].iloc[-8]) / data['Close'].iloc[-8] * 100) if len(data) > 7 else 0,
                
                "rsi": {
                    "value": current_rsi,
                    "signal": "Survente" if current_rsi < 30 else "Surachat" if current_rsi > 70 else "Neutre",
                    "strength": "Fort" if current_rsi < 20 or current_rsi > 80 else "Modéré" if current_rsi < 35 or current_rsi > 65 else "Faible"
                },
                
                "macd": {
                    "macd_line": macd_data['macd'].iloc[-1],
                    "signal_line": macd_data['signal'].iloc[-1],
                    "histogram": macd_data['histogram'].iloc[-1],
                    "signal": "Achat" if macd_data['macd'].iloc[-1] > macd_data['signal'].iloc[-1] else "Vente"
                },
                
                "moving_averages": {
                    "sma_20": ma_data['sma_20'].iloc[-1],
                    "sma_50": ma_data['sma_50'].iloc[-1],
                    "sma_200": ma_data['sma_200'].iloc[-1],
                    "signal": "Haussier" if current_price > ma_data['sma_20'].iloc[-1] > ma_data['sma_50'].iloc[-1] else "Baissier"
                },
                
                "support_resistance": sr_data,
                
                "patterns": patterns,
                
                "overall_signal": self.generate_overall_signal(rsi, macd_data, ma_data, patterns, current_price)
            }
            
            return signals
            
        except Exception as e:
            return {"error": f"Erreur analyse technique pour {symbol}: {e}"}
    
    def generate_overall_signal(self, rsi: pd.Series, macd_data: Dict, ma_data: Dict, patterns: Dict, current_price: float) -> str:
        """Génère un signal global basé sur tous les indicateurs"""
        try:
            score = 0
            
            # RSI
            current_rsi = rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50
            if current_rsi < 30:
                score += 2  # Signal d'achat fort
            elif current_rsi < 40:
                score += 1  # Signal d'achat modéré
            elif current_rsi > 70:
                score -= 2  # Signal de vente fort
            elif current_rsi > 60:
                score -= 1  # Signal de vente modéré
            
            # MACD
            if macd_data['macd'].iloc[-1] > macd_data['signal'].iloc[-1]:
                score += 1
            else:
                score -= 1
            
            # Moyennes mobiles
            if current_price > ma_data['sma_20'].iloc[-1] > ma_data['sma_50'].iloc[-1]:
                score += 1
            elif current_price < ma_data['sma_20'].iloc[-1] < ma_data['sma_50'].iloc[-1]:
                score -= 1
            
            # Patterns
            if patterns.get('double_bottom', False):
                score += 1
            if patterns.get('double_top', False):
                score -= 1
            
            # Générer le signal final
            if score >= 3:
                return "ACHAT FORT"
            elif score >= 1:
                return "ACHAT"
            elif score <= -3:
                return "VENTE FORTE"
            elif score <= -1:
                return "VENTE"
            else:
                return "NEUTRE"
                
        except Exception as e:
            return "NEUTRE"
    
    def get_market_summary(self, symbols: List[str]) -> Dict:
        """Génère un résumé technique du marché"""
        try:
            summary = {
                "timestamp": datetime.now().isoformat(),
                "total_assets": len(symbols),
                "buy_signals": 0,
                "sell_signals": 0,
                "neutral_signals": 0,
                "assets_analysis": []
            }
            
            for symbol in symbols:
                signals = self.get_technical_signals(symbol)
                if "error" not in signals:
                    summary["assets_analysis"].append(signals)
                    
                    overall = signals.get("overall_signal", "NEUTRE")
                    if "ACHAT" in overall:
                        summary["buy_signals"] += 1
                    elif "VENTE" in overall:
                        summary["sell_signals"] += 1
                    else:
                        summary["neutral_signals"] += 1
            
            # Sentiment global
            if summary["buy_signals"] > summary["sell_signals"]:
                summary["market_sentiment"] = "HAUSSIER"
            elif summary["sell_signals"] > summary["buy_signals"]:
                summary["market_sentiment"] = "BAISSIER"
            else:
                summary["market_sentiment"] = "NEUTRE"
            
            return summary
            
        except Exception as e:
            return {"error": f"Erreur résumé marché: {e}"}

# Instance globale
technical_analysis = TechnicalAnalysis() 