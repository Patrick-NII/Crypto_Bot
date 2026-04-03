# 2026-04-03 - Phase 2 : Trading Engine + Risk Management

## Resume
Implementation complete du moteur de trading (paper + live) et du service de gestion des risques.
5 strategies de trading implementees. Flow complet teste et valide avec des prix live.

## Travail effectue

### Trading Engine (:8004)
- [x] **OrderManager** - Orchestrateur complet : fetch prix -> evaluation risque -> execution -> event Redis
- [x] **PaperTrader** - Simulateur paper trading en memoire (10,000 USDT initial)
  - Market orders : execution immediate au prix courant
  - Limit orders : stockes, executes quand le prix atteint le seuil
  - Stop-loss, Take-profit, Trailing stop, OCO
  - Calcul des frais (0.1%)
  - Verification des balances avant execution
- [x] **ExchangeClient** - Wrapper CCXT unifie (Binance prioritaire pour latence)
  - Place market/limit orders, cancel, get ticker
  - Normalisation des symboles (BTC -> BTC/USDT)
- [x] **API REST** - 6 endpoints ordres + 3 endpoints strategies
- [x] Background task : verification des ordres pending toutes les 30s

### Strategies de Trading (5 implementees)
- [x] **MomentumRsiMacd** - RSI + MACD crossover, trend following
- [x] **GridTrading** - Grille d'ordres pour marches lateraux
- [x] **MeanReversion** - Bollinger Bands, retour a la moyenne
- [x] **IntelligentDCA** - DCA dynamique (buy more on dips, less on pumps)
- [x] **SmaCrossover** - Croisement SMA court/long terme

### Risk Service (:8005)
- [x] **RiskCalculator** - Calculs de risque complets :
  - Position sizing (Kelly Criterion)
  - Stop-loss ATR-based
  - Value at Risk (VaR historique)
  - Max drawdown (peak-to-trough)
  - Sharpe ratio (annualise)
  - Volatilite (annualisee)
  - Take-profit multi-niveaux (25%/50%/25%)
- [x] **RiskMonitor** - Monitoring portfolio + alertes
- [x] **Trade Evaluation** - Verification complete avant chaque trade
  - Position size vs portfolio
  - Daily trade limit
  - Drawdown check
  - Concentration check
- [x] **3 profils** : Conservative, Moderate, Aggressive
- [x] **API REST** - 6 endpoints (profile, evaluate, metrics, stop-loss, take-profit)

### Integration inter-services
- [x] Trading Engine -> Market Data Service (fetch prix live)
- [x] Trading Engine -> Risk Service (evaluation avant execution)
- [x] Events Redis pub/sub (ORDER_CREATED, ORDER_FILLED, ORDER_CANCELLED)

## Tests effectues
- Market buy BTC : 0.01 BTC achete a 66,849.67 EUR ✅
- Market sell BTC : 0.005 BTC vendu a 66,852.79 EUR ✅
- Limit buy ETH : Ordre ouvert a 1,700 EUR (en attente) ✅
- Balance tracking : USDT + BTC corrects apres operations ✅
- Risk evaluation : Trade approuve avec risk_score 0.24 ✅
- Risk profile : 3 presets retournes correctement ✅
- Fear & Greed Index : Donnees live (Extreme Fear = 9) ✅

## Bugs rencontres et corriges
1. **URL market-data incorrecte** dans order_manager.py
   - Bug: `/api/v1/crypto/price/` au lieu de `/api/v1/prices/`
   - Fix: Corrige l'URL + parsing de la reponse imbriquee `{data: {price: ...}}`

2. **Python 3.9 incompatibilite** (25 fichiers)
   - Bug: `X | None`, `list[x]`, `dict[x,y]` = syntaxe Python 3.10+
   - Fix: Script de conversion automatique vers `Optional[X]`, `List[x]`, `Dict[x,y]`
   - Bug secondaire: imports `from typing` inseres au milieu de blocs multi-lignes
   - Fix: Correction manuelle des 3 fichiers portfolio-service concernes

3. **aiohttp version conflict** avec ccxt
   - Bug: ccxt 4.4.35 requiert aiohttp<=3.10.11, on avait pin 3.11.11
   - Fix: Pin aiohttp<=3.10.11

4. **Port PostgreSQL conflit** avec instance locale
   - Fix: Port expose change de 5432 a 5433

## Etat du projet
- **Services operationnels** : Gateway, Auth, Portfolio, Market Data, Trading Engine, Risk Service
- **Services stub** : ML, Notification (stub fonctionnel avec Telegram sender)
- **Mode** : Paper trading actif (10,000 USDT simulees)
- **Strategies** : 5 implementees et enregistrees

## Prochaines etapes (Phase 3)
1. Interface Web Glass UI (Next.js + Tailwind + TradingView charts)
2. Dashboard temps reel (WebSocket)
3. Pages portfolio, trades, strategies, alertes
4. Design system glassmorphism mobile-first

## Notes de reprise
- Le trading engine utilise le prix live de CoinGecko via market-data-service
- Paper trader stocke tout en memoire (perdu au redemarrage)
- Pour trader en live : configurer BINANCE_API_KEY/SECRET + TRADING_MODE=live
- Les strategies sont dans `services/trading-engine/app/strategies/`
- L'evaluation de risque est appelee avant chaque ordre automatiquement
- Redis est optionnel (events non publies si Redis absent, mais le trading fonctionne)
