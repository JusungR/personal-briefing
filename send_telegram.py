import os
import sys
import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

text = sys.stdin.read().strip()

if not TOKEN or not CHAT_ID:
    print("텔레그램 발송 건너뜀: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID 환경변수 미설정")
else:
    r = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text, "parse_mode": "Markdown"}
    )
    print(r.status_code, r.text)
