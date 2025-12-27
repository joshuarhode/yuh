
from __future__ import annotations

import json

import os

import urllib.request



def log(event: dict):

    print(json.dumps(event, default=str))



def alert(text: str):

    token = os.getenv("TELEGRAM_BOT_TOKEN")

    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token or not chat_id:

        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})

    try:

        urllib.request.urlopen(req, timeout=10).read()

    except Exception:

        pass

