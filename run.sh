#!/bin/bash
set -e

cd /Users/nii/Documents/Crypto_Bot
source env/bin/activate
export $(grep -v '^#' .env | xargs)

LOG_FILE="/Users/nii/Documents/Crypto_Bot/logs/cron.log"

run_and_log () {
    SCRIPT=$1
    echo "[$(date)] Lancement $SCRIPT" >> $LOG_FILE
    if ! python3 $SCRIPT >> $LOG_FILE 2>&1; then
        curl -s -X POST https://api.telegram.org/bot$TOKEN/sendMessage \
            -d chat_id="$CHAT_ID" \
            -d text="❌ Erreur dans $SCRIPT depuis run.sh"
    fi
}

run_and_log info_wallet.py
run_and_log analyse_marche.py
run_and_log analyse_opportunites.py