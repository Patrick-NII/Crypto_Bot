# Okamoey - Plateforme de Gestion d'Actifs Crypto

## 🚀 Vue d'ensemble

Okamoey est une plateforme professionnelle de gestion d'actifs crypto combinant :
- 🤖 IA avancée pour l'analyse de marché
- 📊 Surveillance en temps réel
- 🎯 Détection d'opportunités d'investissement
- 📱 Bot Telegram intelligent
- 📚 Système RAG pour l'enrichissement des analyses

## 🏗️ Architecture

```
okamoey/
├── core/           # Cœur du système
├── services/       # Services métier
├── monitoring/     # Surveillance et alertes
├── data/          # Données et sources
└── tools/         # Outils utilitaires
```

## 🚀 Installation

1. **Cloner le projet**
```bash
git clone <repository>
cd okamoey
```

2. **Installer les dépendances**
```bash
pip install -r requirements.txt
```

3. **Configurer l'environnement**
```bash
cp .env.example .env
# Éditer .env avec vos clés API
```

4. **Configurer les cron jobs**
```bash
python tools/scripts/setup_cron.py install
```

5. **Lancer le bot**
```bash
python -m core.bot
```

## 📊 Fonctionnalités

### 🔍 Surveillance Continue
- Surveillance des 40 actifs prioritaires
- Alertes automatiques sur signaux techniques
- Analyse sentiment marché

### 🚀 Opportunités d'Investissement
- Analyse fondamentale avancée
- Scoring multi-critères (80%+ confiance)
- Recommandations personnalisées

### 🤖 IA Avancée
- Analyse contextuelle avec sources RAG
- Prédictions basées sur données historiques
- Conseils personnalisés par profil

## 💰 Monétisation

- Abonnements premium
- API payante pour intégrations
- Services conseil personnalisés
- Formation et éducation

## 📞 Support

Pour toute question ou support, contactez-nous via le bot Telegram.

---
*Okamoey - Votre assistant portfolio intelligent* 🎯
