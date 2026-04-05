#!/bin/bash

# Script wrapper pour le cron
cd /Users/nii/Documents/Crypto_Bot

# Activer l'environnement virtuel
source env/bin/activate

# Charger les variables d'environnement
export $(grep -v '^#' .env | xargs)

# Exécuter le script principal
./run.sh 