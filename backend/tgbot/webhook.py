# -*- coding: utf-8 -*-
import hmac
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from telegram import Update

from app.config import settings
from core.dedupe import claim_update
from .runner import ALLOWED_UPDATES, build_app

logger = logging.getLogger("bot")

WEBHOOK_PATH = "/telegram/webhook"
# Host ficticio: com ASGITransport as tools chamam o app em processo.
INTERNAL_API_BASE_URL = "http://internal"

router = APIRouter(tags=["telegram"])


@router.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.telegram_webhook_secret
    if not expected or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=403, detail="Segredo do webhook inválido.")

    if settings.serverless:
        return await _process_inline(request)

    ptb = getattr(request.app.state, "telegram_app", None)
    if ptb is None:
        raise HTTPException(status_code=503, detail="Bot não está ativo.")

    # Enfileira e responde na hora: o processamento (LLM) roda em background
    # na Application, entao o Telegram nao estoura timeout nem reenvia.
    update = Update.de_json(await request.json(), ptb.bot)
    await ptb.update_queue.put(update)
    return {"ok": True}


async def _process_inline(request: Request) -> dict:
    """Serverless: processa o update antes de responder. Uma Application por
    requisicao (o event loop nao e garantido entre invocacoes)."""
    if settings.telegram_mode != "webhook":
        raise HTTPException(status_code=503, detail="Bot não está ativo.")

    payload = await request.json()
    ptb = build_app(
        api_base_url=INTERNAL_API_BASE_URL,
        api_transport=httpx.ASGITransport(app=request.app),
        webhook=True,
    )
    await ptb.initialize()
    try:
        update = Update.de_json(payload, ptb.bot)
        if not claim_update(f"telegram:{update.update_id}"):
            logger.info("Update %s repetido, ignorado", update.update_id)
            return {"ok": True}
        await ptb.process_update(update)
    except Exception:
        # 200 mesmo assim: senao o Telegram reenvia e repete o erro.
        logger.exception("Falha ao processar update do Telegram")
    finally:
        await ptb.shutdown()
    return {"ok": True}


@asynccontextmanager
async def telegram_lifespan(api: FastAPI):
    # Serverless: nada fica rodando; o webhook e registrado por
    # `python -m tgbot.set_webhook <url>`.
    if settings.telegram_mode != "webhook" or settings.serverless:
        api.state.telegram_app = None
        yield
        return

    if not settings.public_base_url:
        raise RuntimeError("TELEGRAM_MODE=webhook exige PUBLIC_BASE_URL (ou RENDER_EXTERNAL_URL).")
    if not settings.telegram_webhook_secret:
        raise RuntimeError("TELEGRAM_MODE=webhook exige TELEGRAM_WEBHOOK_SECRET.")

    ptb = build_app(
        api_base_url=INTERNAL_API_BASE_URL,
        api_transport=httpx.ASGITransport(app=api),
        webhook=True,
    )
    await ptb.initialize()
    url = f"{settings.public_base_url.rstrip('/')}{WEBHOOK_PATH}"
    await ptb.bot.set_webhook(
        url=url,
        secret_token=settings.telegram_webhook_secret,
        allowed_updates=ALLOWED_UPDATES,
    )
    await ptb.start()
    api.state.telegram_app = ptb
    logger.info("Bot ativo em modo webhook: %s", url)
    try:
        yield
    finally:
        await ptb.stop()
        await ptb.shutdown()
        api.state.telegram_app = None
