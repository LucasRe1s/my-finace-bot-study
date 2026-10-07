"""O WhatsApp nao tem comandos nativos: este roteador traduz o texto para as
funcoes do nucleo e envia as respostas."""
import re
from typing import Callable

from app.config import settings
from core.conversation import help_message, invite_command, process_message, process_start
from core.group_chat import process_button
from core.messages import IncomingMessage, OutgoingMessage

from .client import WhatsAppClient
from .parse import WhatsAppEvent

UNSUPPORTED_REPLY = "Por enquanto só entendo mensagens de texto. Escreva o que você precisa, por exemplo: 'gastei R$ 50 no mercado'."
_JOIN = re.compile(r"^join_[A-Za-z0-9-]+$")


def invite_link(number: str) -> Callable[[str], str]:
    # Abre o WhatsApp com "join_<token>" ja digitado; a pessoa so toca em enviar.
    return lambda token: f"https://wa.me/{number}?text=join_{token}"


async def route_text(msg: IncomingMessage, *, api_base_url: str, transport) -> list[OutgoingMessage]:
    text = msg.text.strip()
    if _JOIN.match(text):
        return process_start(msg, text)

    command, _, arg = text.partition(" ")
    command = command.lower().lstrip("/")
    if command == "start":
        return process_start(msg, arg.strip() or None)
    if command == "ajuda" and not arg:
        return help_message(msg)
    if command == "convidar" and not arg:
        return invite_command(msg, invite_link(settings.whatsapp_number))
    return await process_message(
        msg,
        api_base_url=api_base_url,
        transport=transport,
        invite_link=invite_link(settings.whatsapp_number),
    )


async def handle_event(event: WhatsAppEvent, *, client: WhatsAppClient, api_base_url: str, transport) -> None:
    if event.kind == "unsupported":
        outgoing = [OutgoingMessage(chat_id=event.message.chat_id, text=UNSUPPORTED_REPLY)]
    elif event.kind == "button":
        outgoing = process_button(event.message)
    else:
        outgoing = await route_text(event.message, api_base_url=api_base_url, transport=transport)
    await client.send(outgoing)
