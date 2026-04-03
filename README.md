# Okamoey Trading Platform

> Plateforme de trading autonome, auto-correctrice et auto-optimisante pour crypto-monnaies et actions, avec interface web glassmorphism et alertes Telegram.

```
 ██████╗ ██╗  ██╗ █████╗ ███╗   ███╗ ██████╗ ███████╗██╗   ██╗
██╔═══██╗██║ ██╔╝██╔══██╗████╗ ████║██╔═══██╗██╔════╝╚██╗ ██╔╝
██║   ██║█████╔╝ ███████║██╔████╔██║██║   ██║█████╗   ╚████╔╝
██║   ██║██╔═██╗ ██╔══██║██║╚██╔╝██║██║   ██║██╔══╝    ╚██╔╝
╚██████╔╝██║  ██╗██║  ██║██║ ╚═╝ ██║╚██████╔╝███████╗   ██║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝     ╚═╝ ╚═════╝ ╚══════╝   ╚═╝
          AUTONOMOUS TRADING PLATFORM v2.0
```

---

## Table des matieres

- [Vue d'ensemble](#vue-densemble)
- [Architecture](#architecture)
- [Microservices](#microservices)
- [Stack technique](#stack-technique)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [API Documentation](#api-documentation)
- [Strategies de trading](#strategies-de-trading)
- [Gestion des risques](#gestion-des-risques)
- [Systeme d'auto-amelioration](#systeme-dauto-amelioration)
- [Alertes Telegram](#alertes-telegram)
- [Roadmap](#roadmap)
- [Contribuer](#contribuer)

---

## Vue d'ensemble

Okamoey est une plateforme de trading autonome construite en microservices. Elle combine analyse technique, machine learning et gestion des risques pour executer des trades automatiques sur les marches crypto et actions.

### Fonctionnalites principales

| Fonctionnalite | Description | Statut |
|----------------|-------------|--------|
| Trading autonome | Achat/vente automatique multi-exchange | Phase 2 |
| Gestion de portefeuille | CRUD positions, P&L temps reel | Phase 1 ✅ |
| Donnees marche temps reel | WebSocket + multi-source (CCXT, CoinGecko) | Phase 1 ✅ |
| Gestion des risques | Stop-loss, take-profit, VaR, drawdown | Phase 2 |
| Auto-amelioration ML | Backtesting, optimisation, RL | Phase 5 |
| Interface web Glass UI | Dashboard responsive mobile-first | Phase 3 |
| Alertes Telegram | Notifications configurables multi-canal | Phase 4 |
| Authentification JWT | Register, login, refresh tokens | Phase 1 ✅ |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                       │
│                    Glass UI / Mobile First                       │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼──────────────────────────────────────┐
│                      API GATEWAY (:8000)                        │
│              JWT Auth │ Rate Limiting │ Routing                  │
└──┬────┬────┬────┬────┬────┬────┬────────────────────────────────┘
   │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼
┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐┌────┐
│AUTH││PORT││MARK││TRAD││RISK││ ML ││NOTI│
│    ││FOLI││ET  ││ING ││    ││    ││FIC.│
│8001││8002││8003││8004││8005││8006││8007│
└──┬─┘└──┬─┘└──┬─┘└──┬─┘└──┬─┘└──┬─┘└──┬─┘
   │     │     │     │     │     │     │
   ▼     ▼     ▼     ▼     ▼     ▼     ▼
┌─────────────────────────────────────────┐
│            PostgreSQL + TimescaleDB     │
│                   Redis                 │
└─────────────────────────────────────────┘
```

### Communication inter-services

```
┌──────────┐  Redis Pub/Sub  ┌──────────┐
│  Market  │────────────────►│  Trading │
│  Data    │                 │  Engine  │
└──────────┘                 └────┬─────┘
     │                            │
     │ WebSocket                  │ HTTP
     ▼                            ▼
┌──────────┐                ┌──────────┐
│ Frontend │                │   Risk   │
│  (live)  │                │ Service  │
└──────────┘                └────┬─────┘
                                 │
                     Redis Event │
                                 ▼
                           ┌──────────┐
                           │ Notif.   │──► Telegram
                           │ Service  │
                           └──────────┘
```

---

## Microservices

### 1. API Gateway (`:8000`)
Point d'entree unique. Authentification JWT, rate limiting (60 req/min), routage vers les services backend.

### 2. Auth Service (`:8001`)
Gestion des utilisateurs et authentification.
- Inscription / Connexion
- Tokens JWT (access + refresh)
- Profils utilisateur avec niveau de risque

### 3. Portfolio Service (`:8002`)
Gestion complete des portefeuilles et positions.
- CRUD portefeuilles multi-actifs
- Suivi positions (crypto, actions, ETF)
- Calcul P&L temps reel
- Historique transactions
- Allocation par type d'actif

### 4. Market Data Service (`:8003`)
Flux de donnees marche en temps reel.
- Prix via CCXT (Binance prioritaire pour la latence) + CoinGecko fallback
- WebSocket pour streaming temps reel
- Cache Redis (TTL 30s)
- Top marches, trending, Fear & Greed Index
- Historique OHLCV multi-timeframe

### 5. Trading Engine (`:8004`) - *Phase 2*
Moteur d'execution des ordres.
- Ordres : Market, Limit, Stop-Loss, Take-Profit, Trailing Stop, OCO
- Multi-exchange via CCXT
- Mode paper trading / live
- Strategies pluggables (Grid, Momentum, Mean Reversion, etc.)

### 6. Risk Service (`:8005`) - *Phase 2*
Gestion avancee des risques.
- Stop-loss dynamique (ATR-based)
- Take-profit multi-niveaux (25%, 50%, 75%, 100%)
- Value at Risk (VaR) Monte Carlo
- Max drawdown automatique
- Position sizing (Kelly Criterion)
- Correlation portfolio

### 7. ML Service (`:8006`) - *Phase 5*
Pipeline d'auto-amelioration.
- Backtesting automatique
- Optimisation des parametres de strategies
- Reinforcement Learning (PPO/DQN)
- A/B testing de strategies
- Model registry avec versionning

### 8. Notification Service (`:8007`)
Alertes et notifications Telegram.
- Alertes prix (seuils positifs/negatifs)
- Alertes execution (achat/vente)
- Alertes risque (stop-loss, drawdown)
- Signaux ML (opportunites)
- Rapport quotidien portfolio

---

## Stack technique

| Couche | Technologie | Role |
|--------|-------------|------|
| Backend | **FastAPI** (Python 3.12) | API async haute performance |
| Base de donnees | **PostgreSQL 16** + **TimescaleDB** | Donnees relationnelles + series temporelles |
| Cache / Pub-Sub | **Redis 7** | Cache prix, rate limiting, events |
| Exchange API | **CCXT** | Interface unifiee 100+ exchanges |
| ML | **scikit-learn** + **stable-baselines3** | Optimisation + Reinforcement Learning |
| Frontend | **Next.js 14** + **TypeScript** | Interface web SSR |
| UI | **Tailwind CSS** + **Radix UI** | Glassmorphism design system |
| Charts | **TradingView Lightweight** | Graphiques financiers |
| Notifications | **Telegram Bot API** | Alertes temps reel |
| Conteneurisation | **Docker Compose** | Orchestration locale |

---

## Installation

### Pre-requis

- **Docker** >= 24.0 et **Docker Compose** >= 2.20
- **Python** >= 3.12 (pour le developpement local)
- **Node.js** >= 20 (pour le frontend, Phase 3)
- **Git**

### Cloner le projet

```bash
git clone https://github.com/Patrick-NII/Crypto_Bot.git
cd Crypto_Bot
```

### Configuration des variables d'environnement

```bash
cp .env.example .env
# Editer .env avec vos cles API et secrets
```

**Variables requises :**

| Variable | Description | Obligatoire |
|----------|-------------|:-----------:|
| `SECRET_KEY` | Cle secrete application | Oui |
| `JWT_SECRET_KEY` | Cle secrete JWT | Oui |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | Oui |
| `TELEGRAM_BOT_TOKEN` | Token bot Telegram | Non* |
| `TELEGRAM_CHAT_ID` | ID chat Telegram | Non* |
| `BINANCE_API_KEY` | Cle API Binance | Non** |
| `BINANCE_API_SECRET` | Secret API Binance | Non** |

\* Requis pour les alertes Telegram
\** Requis pour le trading live, CoinGecko utilise sinon

---

## Lancement

### Avec Docker Compose (recommande)

```bash
# Demarrer tous les services
docker compose up -d

# Verifier le statut
docker compose ps

# Voir les logs
docker compose logs -f

# Arreter
docker compose down
```

### Developpement local (sans Docker)

```bash
# Terminal 1 - Auth Service
cd services/auth-service
pip install -r requirements.txt
uvicorn app.main:app --port 8001 --reload

# Terminal 2 - Portfolio Service
cd services/portfolio-service
pip install -r requirements.txt
uvicorn app.main:app --port 8002 --reload

# Terminal 3 - Market Data Service
cd services/market-data-service
pip install -r requirements.txt
uvicorn app.main:app --port 8003 --reload

# Terminal 4 - Gateway
cd services/gateway
pip install -r requirements.txt
uvicorn app.main:app --port 8000 --reload
```

### Verifier que tout fonctionne

```bash
# Health checks
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Auth
curl http://localhost:8002/health  # Portfolio
curl http://localhost:8003/health  # Market Data
```

---

## API Documentation

Une fois les services lances, la documentation Swagger est disponible :

| Service | Swagger UI | ReDoc |
|---------|-----------|-------|
| Gateway | http://localhost:8000/docs | http://localhost:8000/redoc |
| Auth | http://localhost:8001/docs | http://localhost:8001/redoc |
| Portfolio | http://localhost:8002/docs | http://localhost:8002/redoc |
| Market Data | http://localhost:8003/docs | http://localhost:8003/redoc |

### Exemples d'utilisation

```bash
# 1. Creer un compte
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "trader@okamoey.com", "username": "trader", "password": "SecurePass123!"}'

# 2. Se connecter
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "trader@okamoey.com", "password": "SecurePass123!"}' | jq -r '.access_token')

# 3. Creer un portefeuille
curl -X POST http://localhost:8000/api/v1/portfolios \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Crypto Principal", "description": "Mon portefeuille crypto"}'

# 4. Ajouter une position
curl -X POST http://localhost:8000/api/v1/positions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"portfolio_id": "...", "symbol": "BTC", "asset_type": "crypto", "quantity": 0.5, "average_entry_price": 62000}'

# 5. Prix en temps reel
curl http://localhost:8000/api/v1/prices?symbols=BTC,ETH,SOL

# 6. WebSocket prix live
wscat -c ws://localhost:8003/ws/prices
```

---

## Strategies de trading

### Strategies implementees (Phase 2+)

| Strategie | Marche | Description |
|-----------|--------|-------------|
| **Grid Trading** | Lateral | Grille d'ordres buy/sell sur plage de prix |
| **Momentum RSI+MACD** | Tendance | Suivi de tendance avec confirmation |
| **Mean Reversion** | Volatil | Retour a la moyenne (Bollinger Bands) |
| **DCA Intelligent** | Tout | Renforcement automatique sur baisses |
| **Arbitrage** | Multi-pair | Profit sur ecarts inter-exchange |
| **Ichimoku Cloud** | Multi-TF | Analyse multi-timeframe |

### Configuration d'une strategie

```json
{
  "strategy": "momentum_rsi_macd",
  "symbol": "BTC",
  "parameters": {
    "rsi_period": 14,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "position_size_pct": 5.0,
    "stop_loss_pct": 3.0,
    "take_profit_pct": 9.0
  },
  "timeframe": "1h",
  "enabled": true
}
```

---

## Gestion des risques

```
                    ┌─────────────────────┐
                    │   ORDRE ENTRANT     │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Position Sizing    │ Kelly Criterion
                    │  Max 10% portfolio  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Correlation Check  │ Diversification
                    │  Max secteur: 30%   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  VaR Check          │ Monte Carlo
                    │  Max daily VaR: 5%  │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Stop-Loss Auto     │ ATR-based
                    │  Trailing stop      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  ✅ ORDRE APPROUVE  │
                    └─────────────────────┘
```

### Profils de risque

| Parametre | Conservateur | Modere | Agressif |
|-----------|:------------:|:------:|:--------:|
| Max position | 5% | 10% | 20% |
| Stop-loss | 3% | 5% | 8% |
| Take-profit | 6% | 15% | 30% |
| Max drawdown | 8% | 15% | 25% |
| Max levier | 1x | 2x | 5x |
| Risque/trade | 1% | 2% | 5% |

---

## Systeme d'auto-amelioration

```
    ┌────────────────────────────────────────────┐
    │           CYCLE D'AMELIORATION             │
    │                                            │
    │  ┌──────────┐    ┌──────────────────┐      │
    │  │ Donnees  │───►│   Backtesting    │      │
    │  │ Marche   │    │  (1 an hist.)    │      │
    │  └──────────┘    └────────┬─────────┘      │
    │                           │                │
    │  ┌──────────┐    ┌───────▼──────────┐      │
    │  │ Trading  │◄───│  Optimisation    │      │
    │  │  Live    │    │  Parametres      │      │
    │  └────┬─────┘    └───────▲──────────┘      │
    │       │                  │                 │
    │  ┌────▼─────┐    ┌──────┴──────────┐      │
    │  │ Resultats│───►│  Performance    │      │
    │  │ Reels    │    │  Tracker        │      │
    │  └──────────┘    └─────────────────┘      │
    │                                            │
    │  Frequence: dynamique (volatile=+ souvent) │
    └────────────────────────────────────────────┘
```

Le ML Service ajuste automatiquement :
- **Parametres des strategies** (RSI periods, seuils, etc.)
- **Allocation par strategie** (poids relatifs)
- **Frequence de reoptimisation** (plus souvent en marche volatile)
- **Selection de strategies** (A/B testing continu)

---

## Alertes Telegram

### Types d'alertes

| Icone | Type | Exemple |
|:-----:|------|---------|
| 📉 | Seuil negatif | "BTC -5.2% en 1h" |
| 📈 | Seuil positif | "SOL +12% depuis achat" |
| 🎯 | Opportunite ML | "Signal achat ETH - Confiance 87%" |
| ✅ | Trade execute | "Achete 0.5 ETH a 3,420 EUR" |
| 🛑 | Stop-loss | "STOP-LOSS ARB declenche a 1.12 EUR" |
| 📊 | Rapport quotidien | Portfolio complet + P&L |
| ⚠️ | Risque | "VaR depasse - Rebalancing suggere" |

---

## Roadmap

- [x] **Phase 1** - Fondation (Auth + Portfolio + Market Data + Gateway)
- [ ] **Phase 2** - Trading Engine + Risk Management
- [ ] **Phase 3** - Interface Web Glass UI (Dashboard + Portfolio)
- [ ] **Phase 4** - Alertes Telegram enrichies
- [ ] **Phase 5** - ML Pipeline + Backtesting + Auto-optimisation
- [ ] **Phase 6** - Analytics avancees + RL + Frequence dynamique

---

## Structure du projet

```
okamoey-trading/
├── services/
│   ├── gateway/             # API Gateway (:8000)
│   ├── auth-service/        # Authentification (:8001)
│   ├── portfolio-service/   # Portefeuilles (:8002)
│   ├── market-data-service/ # Donnees marche (:8003)
│   ├── trading-engine/      # Execution ordres (:8004)
│   ├── risk-service/        # Gestion risques (:8005)
│   ├── ml-service/          # Machine Learning (:8006)
│   └── notification-service/# Notifications (:8007)
├── frontend/                # Next.js (Phase 3)
├── shared/                  # Schemas partages
├── infra/                   # Scripts & config infra
├── worklog/                 # Journal de travail
├── docker-compose.yml       # Orchestration
├── .env.example             # Template variables
└── README.md
```

---

## Contribuer

1. Creer une branche depuis `main`
2. Developper la fonctionnalite
3. Tester localement avec `docker compose up`
4. Creer une Pull Request
5. Consulter `worklog/` pour le contexte

---

**Okamoey Trading Platform** - Built with precision for autonomous trading.
