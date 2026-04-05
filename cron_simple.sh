#!/bin/bash
cd /Users/nii/Documents/Crypto_Bot
source env/bin/activate
export $(grep -v "^#" .env | xargs)
./run.sh 