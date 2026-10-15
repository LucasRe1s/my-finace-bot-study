# -*- coding: utf-8 -*-
"""Registra o webhook do bot no Telegram (deploy serverless).

Uso: python -m tgbot.set_webhook https://sua-api.vercel.app
Le TELEGRAM_BOT_TOKEN e TELEGRAM_WEBHOOK_SECRET do .env.
"""
import re
import sys

import httpx

from app.config import settings

from .runner import ALLOWED_UPDATES
from .webhook import WEBHOOK_PATH

# O Telegram so aceita estes caracteres no secret_token.
SECRET_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,256}$")


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 1
    if not SECRET_PATTERN.match(settings.telegram_webhook_secret):
        print("TELEGRAM_WEBHOOK_SECRET ausente ou invalido (so letras, numeros, _ e -).")
        return 1

    url = f"{argv[0].rstrip('/')}{WEBHOOK_PATH}"
    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook",
        json={
            "url": url,
            "secret_token": settings.telegram_webhook_secret,
            "allowed_updates": ALLOWED_UPDATES,
        },
        timeout=20,
    )
    data = response.json()
    print(f"Webhook registrado: {url}" if data.get("ok") else f"Erro: {data.get('description')}")
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
