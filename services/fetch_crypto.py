# modules/fetch_crypto.py
import requests
import json

def get_crypto_data(crypto_file='data/wallet_crypto.json'):
    with open(crypto_file) as f:
        crypto_wallet = json.load(f)

    ids = ','.join(crypto_wallet.keys())
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=eur"
    response = requests.get(url)
    prices = response.json()

    crypto_report = []
    total = 0
    for token, amount in crypto_wallet.items():
        if token in prices:
            price = prices[token]['eur']
            value = amount * price
            total += value
            crypto_report.append((token.replace('-', ' ').title(), amount, price, value))

    return crypto_report, total
