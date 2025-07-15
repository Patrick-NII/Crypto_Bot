# 🤖 Okamoey Hybrid Bot - Assistant Portfolio Intelligent

## 🎯 **Vue d'ensemble**

Okamoey est un assistant portfolio intelligent qui combine un **chatbot basique** avec des **capacités avancées** et une **préparation pour l'IA**. Le système fonctionne sur 3 niveaux progressifs :

### 📊 **Architecture 3 Niveaux**

#### **Niveau 1 : Chatbot Basique (✅ Implémenté)**
- ✅ **FAQ** : Questions/réponses prédéfinies
- ✅ **Lexique** : Termes financiers expliqués  
- ✅ **Description** : Fonctionnalités du bot
- ✅ **Commandes rapides** : `/help`, `/portfolio`, etc.
- ✅ **Conversation naturelle** : Salutations, conseils, état du marché

#### **Niveau 2 : IA Contextuelle (🚧 En préparation)**
- 🤖 **Analyses poussées** : GPT avec contexte portefeuille
- 📊 **Surveillance tendances** : Détection patterns
- ⚡ **Alertes intelligentes** : Pump, dump, gaps
- 🎯 **3 profils de risque** : Conservateur, Modéré, Agressif

#### **Niveau 3 : Système Avancé (📋 Planifié)**
- 🗄️ **Base de données** : SQLite/PostgreSQL
- 👤 **Reconnaissance utilisateur** : Multi-utilisateurs
- 💾 **Sauvegarde wallets** : Portefeuilles personnalisés
- 🧠 **Mémoire conversationnelle** : Historique des décisions

---

## 🚀 **Fonctionnalités Actuelles**

### 📱 **Commandes Telegram**
```bash
/start     - Bienvenue et menu principal
/help      - Aide complète
/portfolio - Résumé du portefeuille
/performance - Performance 7j, 30j, année
/risk      - Analyse des risques
/trends    - Tendances détectées
/profiles  - Comparaison des profils de risque
/faq       - Questions fréquentes
```

### 💬 **Conversation Naturelle**
- **Salutations** : "Bonjour", "Comment ça va ?"
- **Questions** : "Qu'est-ce que le DCA ?"
- **Lexique** : "Définition pump", "Que signifie FOMO ?"
- **Conseils** : "Conseils pour diversifier"
- **État marché** : "Comment va le marché ?"

### 🎯 **Profils de Risque**
- **🛡️ Conservateur** : 3-6% rendement, -10% drawdown max
- **⚖️ Modéré** : 6-10% rendement, -20% drawdown max  
- **🚀 Agressif** : 10-20% rendement, -40% drawdown max

---

## 📁 **Structure du Projet**

```
bot_money/
├── 📄 okamoey_hybrid_bot.py     # Bot principal hybride
├── 📄 okamoey_bot.py            # Bot original (reports automatiques)
├── 📁 modules/
│   ├── 📄 chatbot_basic.py      # Chatbot basique (FAQ, lexique)
│   ├── 📄 risk_profiles.py      # Profils de risque
│   ├── 📄 telegram_commands.py  # Commandes et conversation
│   ├── 📄 fetch_crypto.py       # Récupération données crypto
│   ├── 📄 fetch_stocks.py       # Récupération données actions
│   └── 📄 utils.py              # Utilitaires
├── 📁 config/
│   └── 📄 ai_config.py          # Configuration IA future
├── 📁 data/
│   ├── 📄 wallet_crypto.json    # Données crypto
│   ├── 📄 wallet_pea.json       # Données PEA
│   └── 📄 Wallet.actions.json   # Actions Revolut
└── 📁 logs/                     # Logs du bot
```

---

## 🛠️ **Installation et Configuration**

### 1. **Dépendances**
```bash
pip install python-telegram-bot python-dotenv requests yfinance
```

### 2. **Variables d'environnement**
```bash
# .env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHANNEL_ID=your_channel_id

# Pour l'IA future (optionnel)
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

### 3. **Lancement**
```bash
# Bot hybride (recommandé)
python3 okamoey_hybrid_bot.py

# Bot original (reports automatiques)
python3 okamoey_bot.py
```

---

## 🎮 **Utilisation**

### **Démarrage**
1. Envoyez `/start` au bot
2. Utilisez les boutons inline ou tapez des commandes
3. Parlez naturellement pour des questions

### **Exemples d'interaction**
```
👤 "Qu'est-ce que le DCA ?"
🤖 [Explication détaillée du Dollar Cost Averaging]

👤 "Définition pump"
🤖 [Définition du terme crypto "pump"]

👤 "/risk"
🤖 [Analyse de votre profil de risque actuel]

👤 "Comment diversifier ?"
🤖 [Conseils de diversification personnalisés]
```

---

## 🔮 **Roadmap IA**

### **Phase 1 : Intégration OpenAI (Court terme)**
```python
# Exemple d'utilisation future
from config.ai_config import ai_config

if ai_config.is_ai_enabled():
    # Analyse poussée avec GPT
    response = await analyze_with_ai(portfolio_data, user_question)
else:
    # Fallback vers chatbot basique
    response = basic_chatbot.process_basic_message(user_question)
```

### **Phase 2 : Analyse Avancée (Moyen terme)**
- 📊 **Analyse technique** : Patterns, signaux
- 🎯 **Recommandations personnalisées** : Basées sur le profil
- ⚡ **Alertes intelligentes** : Détection automatique d'opportunités
- 📈 **Prédictions de tendances** : Analyse de marché

### **Phase 3 : Système Complet (Long terme)**
- 🗄️ **Base de données** : Stockage utilisateurs et portefeuilles
- 👤 **Multi-utilisateurs** : Gestion de plusieurs comptes
- 🧠 **Mémoire conversationnelle** : Historique des décisions
- 📊 **Dashboard web** : Interface d'administration

---

## 💡 **Avantages du Système Hybride**

### **✅ Avantages**
- **Rapidité** : Réponses instantanées pour les questions basiques
- **Fiabilité** : Pas de dépendance à l'IA pour les fonctionnalités essentielles
- **Coût** : Réduction des appels API coûteux
- **Évolutivité** : Ajout progressif de l'IA
- **Fallback** : Système de secours si l'IA est indisponible

### **🎯 Cas d'usage**
- **Questions simples** → Chatbot basique (rapide, gratuit)
- **Analyses complexes** → IA (précise, contextuelle)
- **Urgences** → Chatbot basique (toujours disponible)

---

## 🔧 **Configuration Avancée**

### **Personnalisation des Profils de Risque**
```python
# modules/risk_profiles.py
self.profiles = {
    "conservateur": {
        "max_crypto": 15,      # % max crypto
        "max_single_asset": 10, # % max par actif
        "target_bonds": 40,     # % obligations cible
    }
    # ... autres profils
}
```

### **Ajout de Questions FAQ**
```python
# modules/chatbot_basic.py
self.faq = {
    "nouvelle_question": {
        "question": "Votre question ?",
        "answer": "Votre réponse détaillée..."
    }
}
```

### **Configuration IA**
```python
# config/ai_config.py
self.openai_config = {
    "model": "gpt-4-turbo-preview",
    "max_tokens": 1000,
    "temperature": 0.7,
    # ... autres paramètres
}
```

---

## 🚨 **Sécurité et Bonnes Pratiques**

### **✅ Recommandations**
- 🔐 **Variables d'environnement** : Ne jamais commiter les clés API
- 📊 **Données sensibles** : Chiffrer les informations utilisateur
- 🔄 **Backup** : Sauvegarder régulièrement les données
- 📝 **Logs** : Surveiller les activités du bot
- 🧪 **Tests** : Tester avant déploiement

### **⚠️ Limitations**
- **Télégram** : Les bots ne peuvent pas lire les messages de groupe
- **IA** : Coûts variables selon l'utilisation
- **Données** : Dépendance aux APIs externes

---

## 🤝 **Contribution**

### **Ajout de Fonctionnalités**
1. Créez une branche pour votre fonctionnalité
2. Implémentez dans le module approprié
3. Testez avec `python3 -c "from modules.xxx import *"`
4. Documentez dans ce README
5. Faites une pull request

### **Structure des Modules**
- **chatbot_basic.py** : Questions/réponses prédéfinies
- **risk_profiles.py** : Logique des profils de risque
- **telegram_commands.py** : Commandes et conversation
- **ai_config.py** : Configuration IA future

---

## 📞 **Support**

### **Problèmes Courants**
- **Bot ne répond pas** : Vérifiez le token et les permissions
- **Erreurs de données** : Vérifiez les fichiers JSON dans `/data`
- **IA non disponible** : Le chatbot basique prend le relais

### **Logs**
```bash
tail -f logs/bot.log  # Suivre les logs en temps réel
```

---

## 🎉 **Conclusion**

Le système hybride Okamoey offre le meilleur des deux mondes :
- **Simplicité** pour les questions basiques
- **Intelligence** pour les analyses complexes
- **Évolutivité** pour les futures améliorations

**Prêt à optimiser vos investissements ?** 🚀

---

*Développé avec ❤️ pour les investisseurs intelligents* 