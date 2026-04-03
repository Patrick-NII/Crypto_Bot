# modules/fetch_stocks.py
import json
import yfinance as yf

def get_stock_data(json_file):
    with open(json_file) as f:
        stocks = json.load(f)

    report = []
    total = 0
    for ticker, info in stocks.items():
        stock = yf.Ticker(ticker)
        try:
            current = stock.history(period="1d")["Close"].iloc[-1]
        except:
            current = 0.0
        amount = info['amount']
        value = amount * current
        pru = info['pru']
        gain = value - (amount * pru)
        total += value
        report.append((ticker, amount, current, value, pru, gain))

    return report, total
