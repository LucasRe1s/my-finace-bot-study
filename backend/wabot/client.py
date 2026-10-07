"""Envio de mensagens pela WhatsApp Cloud API (Graph API)."""
import logging

import httpx

from core.messages import OutgoingMessage

logger = logging.getLogger("bot")

GRAPH_URL = "https://graph.facebook.com"
TEXT_LIMIT = 4096
BUTTON_BODY_LIMIT = 1024
BUTTON_TITLE_LIMIT = 20
MAX_BUTTONS = 3


def _base(out: OutgoingMessage) -> dict:
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": out.chat_id}
    if out.reply_to:
        payload["context"] = {"message_id": out.reply_to}
    return payload


def build_payloads(out: OutgoingMessage) -> list[dict]:
    if out.buttons:
        buttons = [
            {"type": "reply", "reply": {"id": b.action[:256], "title": b.label[:BUTTON_TITLE_LIMIT]}}
            for b in out.buttons[:MAX_BUTTONS]
        ]
        return [{
            **_base(out),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": out.text[:BUTTON_BODY_LIMIT]},
                "action": {"buttons": buttons},
            },
        }]
    chunks = [out.text[i:i + TEXT_LIMIT] for i in range(0, len(out.text), TEXT_LIMIT)] or [""]
    return [{**_base(out), "type": "text", "text": {"body": chunk, "preview_url": False}} for chunk in chunks]


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, version: str, transport: httpx.AsyncBaseTransport | None = None):
        self._url = f"{GRAPH_URL}/{version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._transport = transport

    async def send(self, outgoing: list[OutgoingMessage]) -> None:
        async with httpx.AsyncClient(headers=self._headers, transport=self._transport, timeout=30) as client:
            for out in outgoing:
                for payload in build_payloads(out):
                    response = await client.post(self._url, json=payload)
                    if response.status_code >= 400:
                        # Nao levanta: uma falha de envio nao deve derrubar as proximas mensagens.
                        logger.error(
                            "Falha ao enviar WhatsApp para %s: %s %s",
                            out.chat_id, response.status_code, response.text[:300],
                        )
