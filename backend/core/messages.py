from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    """Mensagem de texto recebida por qualquer canal, ja normalizada."""
    channel: str
    external_user_id: str
    display_name: str
    chat_id: str
    text: str


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
