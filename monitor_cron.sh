#!/bin/bash

echo "=== Monitoring du Cron ==="
echo "Date actuelle: $(date)"
echo ""

echo "=== Crontab actuel ==="
crontab -l
echo ""

echo "=== Dernières exécutions dans les logs ==="
tail -10 logs/cron.log
echo ""

echo "=== Prochaine exécution prévue ==="
# Calculer la prochaine exécution (toutes les 15 minutes)
current_minute=$(date +%M)
current_hour=$(date +%H)
next_minute=$(( (current_minute / 15 + 1) * 15 ))
if [ $next_minute -ge 60 ]; then
    next_minute=0
    next_hour=$((current_hour + 1))
    if [ $next_hour -ge 24 ]; then
        next_hour=0
    fi
else
    next_hour=$current_hour
fi
printf "Prochaine exécution: %02d:%02d\n" $next_hour $next_minute

echo ""
echo "=== Test manuel du script ==="
cd /Users/nii/Documents/Crypto_Bot
if ./run.sh; then
    echo "✅ Script fonctionne correctement"
else
    echo "❌ Erreur dans le script"
fi 