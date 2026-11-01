import json
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

token = os.getenv("TELEGRAM_TOKEN")
if not token:
    sys.exit("Falta TELEGRAM_TOKEN en el entorno (.env).")

r = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo", timeout=15)
info = r.json().get("result", {})
print(json.dumps(info, indent=2, ensure_ascii=False))
print()
print("url:", info.get("url") or "(sin webhook)")
print("updates pendientes:", info.get("pending_update_count"))
print("último error:", info.get("last_error_message") or "ninguno")
