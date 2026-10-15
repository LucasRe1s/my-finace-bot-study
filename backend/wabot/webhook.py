"""Webhook da WhatsApp Cloud API dentro da propria API."""
import hmac
import json
import logging
from collections import OrderedDict

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

from .client import WhatsAppClient
from .dispatch import handle_event
from .parse import WhatsAppEvent, parse_webhook, verify_signature

logger = logging.getLogger("bot")

WEBHOOK_PATH = "/whatsapp/webhook"
# Host ficticio: com ASGITransport as tools chamam o app em processo.
INTERNAL_API_BASE_URL = "http://internal"

router = APIRouter(tags=["whatsapp"])


class RecentIds:
    """Ids ja processados (a Meta reentrega webhooks). Em memoria, um worker."""

    def __init__(self, maxlen: int):
        self._maxlen = maxlen
        self._ids: OrderedDict[str, None] = OrderedDict()

    def seen(self, key: str) -> bool:
        if key in self._ids:
            return True
        self._ids[key] = None
        if len(self._ids) > self._maxlen:
            self._ids.popitem(last=False)
        return False


_recent = RecentIds(2048)


def make_client() -> WhatsAppClient:
    return WhatsAppClient(
        settings.whatsapp_access_token,
        settings.whatsapp_phone_number_id,
        settings.whatsapp_graph_version,
    )


def _require_enabled() -> None:
    if not settings.whatsapp_enabled:
        raise HTTPException(status_code=404)


@router.get(WEBHOOK_PATH)
async def verify_webhook(request: Request):
    _require_enabled()
    params = request.query_params
    token = params.get("hub.verify_token", "")
    if params.get("hub.mode") == "subscribe" and hmac.compare_digest(token, settings.whatsapp_verify_token):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Token de verificação inválido.")


@router.post(WEBHOOK_PATH)
async def receive_webhook(request: Request, background: BackgroundTasks):
    _require_enabled()
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("X-Hub-Signature-256"), settings.whatsapp_app_secret):
        raise HTTPException(status_code=403, detail="Assinatura inválida.")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON inválido.")

    events = [e for e in parse_webhook(payload) if not _recent.seen(e.wamid)]
    if events:
        # Responde 200 na hora; o LLM roda depois, sem a Meta estourar timeout e reenviar.
        background.add_task(_process, events, httpx.ASGITransport(app=request.app))
    return {"ok": True}


async def _process(events: list[WhatsAppEvent], transport: httpx.AsyncBaseTransport) -> None:
    client = make_client()
    for event in events:
        try:
            await handle_event(event, client=client, api_base_url=INTERNAL_API_BASE_URL, transport=transport)
        except Exception:
            logger.exception("Falha ao processar mensagem do WhatsApp %s", event.wamid)
