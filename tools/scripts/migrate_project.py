#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de migration vers la nouvelle structure du projet
"""

import os
import shutil
from pathlib import Path

def migrate_project():
    """Migre les fichiers vers la nouvelle structure"""
    
    project_root = Path(__file__).resolve().parent.parent.parent
    
    print("🔄 Migration vers la nouvelle structure...")
    
    # Mapping des fichiers à migrer
    migrations = [
        # Bot principal
        {
            'source': 'gluetrade_hybrid_bot.py',
            'destination': 'core/bot/main.py',
            'description': 'Bot principal'
        },
        {
            'source': 'gluetrade_bot.py',
            'destination': 'core/bot/legacy.py',
            'description': 'Bot legacy'
        },
        
        # Modules existants
        {
            'source': 'modules/',
            'destination': 'services/',
            'description': 'Modules de services'
        },
        
        # Données
        {
            'source': 'data/',
            'destination': 'data/',
            'description': 'Données existantes'
        },
        
        # Logs
        {
            'source': 'logs/',
            'destination': 'logs/',
            'description': 'Logs existants'
        },
        
        # Configuration
        {
            'source': '.env',
            'destination': '.env',
            'description': 'Variables d\'environnement'
        }
    ]
    
    success_count = 0
    error_count = 0
    
    for migration in migrations:
        source_path = project_root / migration['source']
        dest_path = project_root / migration['destination']
        
        try:
            if source_path.exists():
                # Créer le répertoire de destination si nécessaire
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                
                if source_path.is_dir():
                    # Copier le répertoire
                    if dest_path.exists():
                        shutil.rmtree(dest_path)
                    shutil.copytree(source_path, dest_path)
                else:
                    # Copier le fichier
                    shutil.copy2(source_path, dest_path)
                
                print(f"✅ {migration['description']} migré")
                success_count += 1
            else:
                print(f"⚠️ {migration['source']} non trouvé")
                
        except Exception as e:
            print(f"❌ Erreur migration {migration['source']}: {e}")
            error_count += 1
    
    # Créer les fichiers __init__.py manquants
    init_files = [
        'core/__init__.py',
        'core/bot/__init__.py',
        'core/api/__init__.py',
        'core/database/__init__.py',
        'core/config/__init__.py',
        'services/__init__.py',
        'services/crypto_analysis/__init__.py',
        'services/portfolio_management/__init__.py',
        'services/market_intelligence/__init__.py',
        'services/ai_engine/__init__.py',
        'services/notification/__init__.py',
        'monitoring/__init__.py',
        'monitoring/cron_jobs/__init__.py',
        'monitoring/alerts/__init__.py',
        'monitoring/dashboards/__init__.py',
        'tools/__init__.py',
        'tools/scripts/__init__.py',
        'tools/tests/__init__.py',
        'tools/deployment/__init__.py',
        'docs/__init__.py',
        'docs/api/__init__.py',
        'docs/user_guide/__init__.py',
        'docs/technical/__init__.py'
    ]
    
    for init_file in init_files:
        init_path = project_root / init_file
        init_path.parent.mkdir(parents=True, exist_ok=True)
        init_path.touch()
    
    print(f"\n📊 Résumé de la migration:")
    print(f"✅ Succès: {success_count}")
    print(f"❌ Erreurs: {error_count}")
    
    return success_count > 0

def create_new_files():
    """Crée les nouveaux fichiers de la structure"""
    
    project_root = Path(__file__).resolve().parent.parent.parent
    
    print("\n📝 Création des nouveaux fichiers...")
    
    # Fichiers à créer
    new_files = [
        {
            'path': 'core/bot/__main__.py',
            'content': '''#!/usr/bin/env python3
"""
Point d'entrée principal du bot
"""

from core.bot.main import main

if __name__ == "__main__":
    main()
'''
        },
        {
            'path': 'requirements.txt',
            'content': '''# GlueTrade - Plateforme de Gestion d'Actifs
# Dépendances principales

# Bot Telegram
python-telegram-bot>=22.0

# IA et analyse
openai>=1.0.0
requests>=2.28.0

# Analyse technique
pandas>=1.5.0
numpy>=1.21.0
ta>=0.10.0

# Gestion des sources
PyPDF2>=3.0.0
PyMuPDF>=1.23.0

# Configuration
python-dotenv>=0.19.0

# Logging et monitoring
psutil>=5.9.0

# Tests
pytest>=7.0.0
pytest-asyncio>=0.21.0

# Développement
black>=22.0.0
flake8>=5.0.0
'''
        },
        {
            'path': 'README.md',
            'content': '''# GlueTrade - Plateforme de Gestion d'Actifs Crypto

## 🚀 Vue d'ensemble

GlueTrade est une plateforme professionnelle de gestion d'actifs crypto combinant :
- 🤖 IA avancée pour l'analyse de marché
- 📊 Surveillance en temps réel
- 🎯 Détection d'opportunités d'investissement
- 📱 Bot Telegram intelligent
- 📚 Système RAG pour l'enrichissement des analyses

## 🏗️ Architecture

```
gluetrade/
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
cd gluetrade
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
*GlueTrade - Votre assistant portfolio intelligent* 🎯
'''
        }
    ]
    
    for file_info in new_files:
        file_path = project_root / file_info['path']
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(file_info['content'])
        
        print(f"✅ {file_info['path']} créé")

def main():
    """Fonction principale"""
    print("🔄 Migration du projet GlueTrade")
    print("=" * 50)
    
    # Migrer les fichiers existants
    if migrate_project():
        # Créer les nouveaux fichiers
        create_new_files()
        
        print("\n🎉 Migration terminée avec succès !")
        print("\n📋 Prochaines étapes:")
        print("1. Vérifier la configuration dans .env")
        print("2. Installer les cron jobs: python tools/scripts/setup_cron.py install")
        print("3. Tester le bot: python -m core.bot")
        print("4. Vérifier les logs dans logs/")
    else:
        print("\n❌ Migration échouée")

if __name__ == "__main__":
    main() 