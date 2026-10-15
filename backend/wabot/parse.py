"""Conversao do webhook da WhatsApp Cloud API em eventos do nucleo."""
import hashlib
import hmac
from dataclasses import dataclass

from core.messages import IncomingMessage

CHANNEL = "whatsapp"


def verify_signature(raw: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256: HMAC-SHA256 do corpo cru com o App Secret. Precisa
    ser o corpo exato recebido; JSON re-serializado nao bate."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[len("sha256="):], expected)


@dataclass(frozen=True)
class WhatsAppEvent:
    kind: str  # "text", "button" ou "unsupported"
    message: IncomingMessage
    wamid: str


def parse_webhook(payload: dict) -> list[WhatsAppEvent]:
    events: list[WhatsAppEvent] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts", [])}
            for raw in value.get("messages", []):
                sender, wamid = raw.get("from"), raw.get("id")
                if not sender or not wamid:
                    continue
                kind, text = _kind_and_text(raw)
                events.append(WhatsAppEvent(
                    kind=kind,
                    wamid=wamid,
                    message=IncomingMessage(
                        channel=CHANNEL,
                        external_user_id=sender,
                        display_name=names.get(sender, ""),
                        chat_id=sender,
                        text=text,
                        message_id=wamid,
                    ),
                ))
    return events


def _kind_and_text(raw: dict) -> tuple[str, str]:
    if raw.get("type") == "text":
        return "text", (raw.get("text") or {}).get("body", "")
    interactive = raw.get("interactive") or {}
    if raw.get("type") == "interactive" and interactive.get("type") == "button_reply":
        return "button", interactive["button_reply"].get("id", "")
    return "unsupported", ""
