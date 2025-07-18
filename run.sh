#!/bin/bash

# Activer l'environnement virtuel
source /Users/nii/Documents/Crypto_Bot/env/bin/activate

# Aller dans le dossier du projet
cd /Users/nii/Documents/Crypto_Bot

# Exécuter le script Python
/Users/nii/Documents/Crypto_Bot/env/bin/python3 info_wallet.py >> logs/cron.log 2>&1
