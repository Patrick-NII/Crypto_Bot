# 🚀 Guide d'Utilisation - Plateforme Okamoey

## 📋 Vue d'ensemble

Okamoey est maintenant une **plateforme professionnelle de gestion d'actifs crypto** avec :
- 🤖 **IA avancée** pour l'analyse de marché
- 📊 **Surveillance en temps réel** des 40 actifs prioritaires
- 🎯 **Détection d'opportunités** avec scoring 80%+ confiance
- 📱 **Bot Telegram intelligent** avec commandes avancées
- 📚 **Système RAG** pour enrichir les analyses
- 💰 **Préparé pour la monétisation**

## 🏗️ Nouvelle Architecture

```
okamoey/
├── core/           # Cœur du système
├── services/       # Services métier
├── monitoring/     # Surveillance et alertes
├── data/          # Données et sources
├── tools/         # Outils utilitaires
└── docs/          # Documentation
```

## 🚀 Démarrage Rapide

### 1. **Lancer la plateforme complète**
```bash
python start_okamoey.py
```

### 2. **Arrêter la plateforme**
```bash
python stop_okamoey.py
```

### 3. **Surveillance manuelle**
```bash
# Analyser les opportunités
python monitoring/cron_jobs/simple_monitor.py opportunities

# Mise à jour marché
python monitoring/cron_jobs/simple_monitor.py market

# Tout analyser
python monitoring/cron_jobs/simple_monitor.py all
```

## 📊 Fonctionnalités Premium

### 🔍 **Surveillance Automatique**
- **Toutes les 30 minutes** : Mise à jour marché (BTC/ETH)
- **Toutes les heures** : Analyse opportunités crypto
- **Toutes les 2 heures** : Intelligence de marché
- **Alertes automatiques** sur signaux techniques

### 🎯 **Détection d'Opportunités**
- Analyse fondamentale avancée
- Scoring multi-critères (marché, communauté, développement)
- Seuil de confiance 80% minimum
- Top 5 opportunités recommandées

### 🤖 **IA Avancée**
- Analyse contextuelle avec sources RAG
- Prédictions basées sur données historiques
- Conseils personnalisés par profil
- Enrichissement via PDF uploads

### 📱 **Bot Telegram**
- Commandes `/ai`, `/analyse`, `/opportunities`
- Upload de PDF pour enrichir l'IA
- Gestion des sources avec `/sources`
- Notifications automatiques

## 💰 Stratégie de Monétisation

### 🎯 **Offre Premium**
1. **Abonnements mensuels** : Accès aux analyses avancées
2. **API payante** : Intégrations pour entreprises
3. **Services conseil** : Accompagnement personnalisé
4. **Formation** : Éducation crypto et trading

### 📈 **Valeur Ajoutée**
- Analyses exclusives non disponibles ailleurs
- Alertes en temps réel sur opportunités
- IA spécialisée crypto/stocks uniquement
- Support communautaire premium

## 🔧 Configuration Avancée

### **Variables d'environnement (.env)**
```bash
# Bot Telegram
TOKEN=your_telegram_token
CHAT_ID=your_channel_id

# OpenAI
OPENAI_API_KEY=your_openai_key

# APIs externes (optionnel)
COINGECKO_API_KEY=your_coingecko_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key

# Configuration
ENABLE_CHANNEL_POSTS=true
ENABLE_ALERTS=true
MIN_CONFIDENCE_LEVEL=80.0
```

### **Intervalles de surveillance**
- `CRYPTO_UPDATE_INTERVAL=300` (5 minutes)
- `OPPORTUNITIES_UPDATE_INTERVAL=3600` (1 heure)
- `MARKET_ANALYSIS_INTERVAL=1800` (30 minutes)

## 📊 Logs et Monitoring

### **Fichiers de logs**
- `logs/auto_monitor.log` - Surveillance automatique
- `logs/okamoey.log` - Bot principal
- `logs/monitoring.log` - Analyses manuelles

### **Surveillance des processus**
- Fichier `okamoey.pid` avec les PIDs actifs
- Redémarrage automatique en cas de crash
- Statut toutes les heures dans les logs

## 🎯 Commandes Bot

### **Commandes principales**
- `/start` - Bienvenue et aide
- `/help` - Liste des commandes
- `/ai` - Assistant IA avancé
- `/analyse` - Analyse technique
- `/opportunities` - Opportunités d'investissement
- `/sources` - Gestion des sources RAG

### **Upload de documents**
- Envoyer un PDF au bot
- Extraction automatique du texte
- Indexation pour enrichir l'IA
- Utilisation dans les analyses

## 🔍 Surveillance Manuelle

### **Scripts disponibles**
```bash
# Surveillance simple
python monitoring/cron_jobs/simple_monitor.py opportunities
python monitoring/cron_jobs/simple_monitor.py market
python monitoring/cron_jobs/simple_monitor.py all

# Surveillance automatique
python tools/scripts/auto_monitor.py

# Configuration cron (si disponible)
python tools/scripts/setup_cron.py install
```

## 📈 Métriques de Performance

### **Indicateurs de succès**
- Nombre d'alertes envoyées
- Opportunités détectées
- Utilisation des commandes bot
- Engagement du canal Telegram
- Qualité des analyses IA

### **Optimisations**
- Cache des données API
- Limitation des requêtes
- Gestion des erreurs robuste
- Logs détaillés pour debug

## 🚀 Prochaines Étapes

### **Développement**
1. **Interface web** pour visualisation
2. **API REST** pour intégrations
3. **Base de données** pour historique
4. **Système de paiement** intégré

### **Marketing**
1. **Canal Telegram** actif avec contenu premium
2. **Communauté** d'investisseurs
3. **Partnerships** avec exchanges
4. **Formation** et éducation

## 🆘 Support et Dépannage

### **Problèmes courants**
1. **Bot ne répond pas** → Vérifier TOKEN et CHAT_ID
2. **Analyses vides** → Vérifier OPENAI_API_KEY
3. **Surveillance arrêtée** → Redémarrer avec `start_okamoey.py`
4. **Erreurs API** → Vérifier les limites de requêtes

### **Logs de debug**
```bash
# Voir les logs en temps réel
tail -f logs/auto_monitor.log
tail -f logs/okamoey.log

# Vérifier les processus
ps aux | grep okamoey
```

---

## 🎉 **Okamoey - Votre Assistant Portfolio Intelligent**

La plateforme est maintenant prête pour une utilisation professionnelle et la monétisation. Elle combine IA avancée, surveillance temps réel et analyses exclusives pour offrir une valeur unique dans l'écosystème crypto.

**🚀 Prêt à révolutionner la gestion d'actifs crypto !** 