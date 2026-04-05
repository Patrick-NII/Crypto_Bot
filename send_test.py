import os, requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TOKEN")
chat_id = os.getenv("CHAT_ID")

r = requests.post(
    f"https://api.telegram.org/bot{token}/sendMessage",
    data={"chat_id": chat_id, "text": "TH lisoko na yo !"}
)
print(r.status_code, r.text)