from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    """Mensagem de texto recebida por qualquer canal, ja normalizada."""
    channel: str
    external_user_id: str
    display_name: str
    chat_id: str
    text: str
    chat_type: str = "private"  # "private" ou "group"
    # Em grupo: a mensagem foi dirigida ao bot (resposta, comando ou mencao).
    addressed: bool = True
    message_id: str | None = None


@dataclass(frozen=True)
class Button:
    label: str
    # Enviado de volta ao nucleo quando clicado (Telegram: callback_data, ate 64 bytes).
    action: str


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
    reply_to: str | None = None
    buttons: tuple[Button, ...] = ()
