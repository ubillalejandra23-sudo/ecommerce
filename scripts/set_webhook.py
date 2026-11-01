import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

token = os.getenv("TELEGRAM_TOKEN")
secreto = os.getenv("TELEGRAM_SECRET")
public_url = (os.getenv("PUBLIC_URL") or "").rstrip("/")

if not (token and secreto and public_url):
    sys.exit("Faltan TELEGRAM_TOKEN, TELEGRAM_SECRET o PUBLIC_URL en el entorno (.env).")
if not public_url.startswith("https://"):
    sys.exit("PUBLIC_URL debe ser https.")

r = httpx.post(
    f"https://api.telegram.org/bot{token}/setWebhook",
    json={"url": f"{public_url}/telegram", "secret_token": secreto},
    timeout=15,
)
print(r.status_code, r.text)
