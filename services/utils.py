# modules/utils.py
from datetime import datetime

def format_currency(val):
    return f"{val:,.2f} €".replace(",", " ").replace(".", ",")

def log_report(content):
    now = datetime.now().strftime("%Y-%m-%d")
    with open(f"logs/{now}.txt", "a") as f:
        f.write(content + "\n\n")