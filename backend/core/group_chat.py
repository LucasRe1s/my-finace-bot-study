"""Regras do bot dentro de um chat de grupo ligado a um grupo financeiro."""
import logging

from app.database import get_service_supabase
from app.services.chat_bindings import (
    ChatAlreadyBound,
    ChatNotBound,
    GroupAlreadyBound,
    NotGroupOwner,
    bind_chat,
    find_binding,
    move_chat,
    unbind_chat,
)
from app.services.identities import get_or_create_user
from app.services.membership import find_user_group, get_group, names_by_id

from .messages import Button, IncomingMessage, OutgoingMessage

logger = logging.getLogger("bot")

APPROVE_PREFIX = "approve:"
NOT_BOUND_REPLY = (
    "Este chat ainda não está ligado a um grupo financeiro. "
    "O dono do grupo financeiro precisa enviar /vincular aqui."
)
GROUP_WELCOME = (
    "Olá! Sou o Assistente Financeiro.\n\n"
    "Para começar, o dono do grupo financeiro envia /vincular aqui.\n"
    "Depois, para falar comigo neste chat, responda a uma mensagem minha "
    "ou use /f, por exemplo: /f gastei R$ 50 no mercado."
)


def chat_key(msg: IncomingMessage) -> str:
    return f"{msg.channel}:{msg.chat_id}"


def _reply(msg: IncomingMessage, text: str, buttons: tuple[Button, ...] = ()) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=text, reply_to=msg.message_id, buttons=buttons)]


def group_access_refusal(db, msg: IncomingMessage, user: dict) -> list[OutgoingMessage] | None:
    """None se o remetente pode usar o bot neste chat; senao, a resposta."""
    binding = find_binding(db, msg.channel, msg.chat_id)
    if binding is None:
        return _reply(msg, NOT_BOUND_REPLY)

    user_group = find_user_group(db, user["id"])
    if user_group == binding["group_id"]:
        return None
    if user_group is not None:
        return _reply(msg, "Você participa de outro grupo financeiro, então não posso registrar seus lançamentos aqui.")

    group = get_group(db, binding["group_id"]) or {}
    name = user.get("name") or msg.display_name or "Esta pessoa"
    return _reply(
        msg,
        f"{name} ainda não participa do grupo financeiro {group.get('name', '')}. "
        "O dono do grupo pode aprovar pelo botão abaixo.",
        buttons=(Button(label=f"Aprovar {name}", action=f"{APPROVE_PREFIX}{user['id']}"),),
    )


def process_button(msg: IncomingMessage) -> list[OutgoingMessage]:
    if not msg.text.startswith(APPROVE_PREFIX):
        return []
    target_id = msg.text[len(APPROVE_PREFIX):]
    db = get_service_supabase()
    try:
        approver, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        binding = find_binding(db, msg.channel, msg.chat_id)
        if binding is None:
            return _reply(msg, NOT_BOUND_REPLY)
        group = get_group(db, binding["group_id"])
        if group is None or group["owner_id"] != approver["id"]:
            return _reply(msg, "Só o dono do grupo financeiro pode aprovar novos membros.")
        name = names_by_id(db, [target_id]).get(target_id) or "Novo membro"
        if find_user_group(db, target_id) is not None:
            return _reply(msg, f"{name} já participa de um grupo financeiro.")
        db.table("group_members").insert({"group_id": group["id"], "user_id": target_id, "role": "member"}).execute()
    except Exception:
        logger.exception("Falha ao aprovar membro no chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível aprovar agora. Tente novamente em instantes.")
    return _reply(msg, f"{name} agora faz parte do grupo {group['name']}.")


def bind_command(msg: IncomingMessage) -> list[OutgoingMessage]:
    if msg.chat_type != "group":
        return _reply(msg, "Use /vincular dentro do grupo do Telegram que você quer ligar ao grupo financeiro.")
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group = bind_chat(db, msg.channel, msg.chat_id, user["id"])
    except NotGroupOwner:
        return _reply(msg, (
            "Só o dono de um grupo financeiro pode vincular este chat. "
            "Crie o grupo financeiro falando comigo no privado e depois envie /vincular aqui."
        ))
    except ChatAlreadyBound:
        return _reply(msg, "Este chat já está vinculado a um grupo financeiro.")
    except GroupAlreadyBound:
        return _reply(msg, "Seu grupo financeiro já está vinculado a outro chat. Envie /desvincular lá primeiro.")
    except Exception:
        logger.exception("Falha ao vincular chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível vincular agora. Tente novamente em instantes.")
    return _reply(msg, (
        f"Chat vinculado ao grupo financeiro {group['name']}.\n\n"
        "Para falar comigo aqui, responda a uma mensagem minha ou use /f, "
        "por exemplo: /f gastei R$ 50 no mercado. "
        "Quem ainda não participa do grupo financeiro será aprovado por você."
    ))


def unbind_command(msg: IncomingMessage) -> list[OutgoingMessage]:
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        unbind_chat(db, msg.channel, msg.chat_id, user["id"])
    except ChatNotBound:
        return _reply(msg, "Este chat não está vinculado a nenhum grupo financeiro.")
    except NotGroupOwner:
        return _reply(msg, "Só o dono do grupo financeiro pode desvincular este chat.")
    except Exception:
        logger.exception("Falha ao desvincular chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível desvincular agora. Tente novamente em instantes.")
    return _reply(msg, "Chat desvinculado. Os dados do grupo financeiro continuam salvos.")


def group_welcome(msg: IncomingMessage) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=GROUP_WELCOME)]


def chat_migrated(channel: str, old_chat_id: str, new_chat_id: str) -> None:
    move_chat(get_service_supabase(), channel, old_chat_id, new_chat_id)
