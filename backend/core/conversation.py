"""Nucleo de conversa, independente de canal. Adaptadores (tgbot/, e o
WhatsApp na Fase 5) convertem a mensagem do canal em IncomingMessage e enviam
as OutgoingMessage devolvidas."""
import logging
from typing import Callable

from agent.bot import create_agent
from agent.history import get_history, save_history
from agent.tools import build_tools, is_raw_provider_error, resolve_leaked_tool_call
from app.database import get_service_supabase
from app.services.invites import AlreadyInGroup, InviteNotFound, accept_invite, create_invite
from app.services.identities import InvalidLinkCode, LinkConflict, get_or_create_user, link_identity
from app.services.membership import find_user_group, group_name
from app.services.user_token import generate_user_token

from .messages import IncomingMessage, OutgoingMessage
from .rate_limit import SlidingWindowLimiter

logger = logging.getLogger("bot")

FALLBACK_REPLY = "Desculpe, tive um problema para processar sua mensagem. Pode tentar novamente?"
RATE_LIMIT_REPLY = "Você enviou muitas mensagens em pouco tempo. Aguarde alguns minutos e tente novamente."
JOIN_PREFIX = "join_"
HELP_TEXT = (
    "Comandos disponíveis:\n\n"
    "/start: iniciar ou reiniciar o assistente\n"
    "/convidar: gerar link de convite para um familiar\n"
    "/ajuda: exibir esta mensagem\n\n"
    "O que posso fazer por você:\n"
    "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')\n"
    "- Desfazer o último lançamento ('Desfaz o último')\n"
    "- Consultar saldo do mês ('Qual meu saldo?')\n"
    "- Ver extrato ('Mostre meus gastos de junho')\n"
    "- Resumo por categoria ('Quanto gastei com alimentação?')\n"
    "- Definir limites ('Limite de R$ 500 para Alimentação')\n"
    "- Ver limites ('Quais são meus limites?')"
)

# Protege a cota do provedor do LLM: 30 mensagens a cada 10 minutos por pessoa.
limiter = SlidingWindowLimiter(max_events=30, window_seconds=600)


def _reply(msg: IncomingMessage, text: str) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=text)]


def _with_history(history: list[dict], text: str) -> str:
    if not history:
        return f"Usuário: {text}"
    lines = ["", "", "[Histórico recente da conversa:]"]
    for item in history:
        role = "Usuário" if item["role"] == "user" else "Assistente"
        lines.append(f"{role}: {item['content']}")
    lines += ["[Fim do histórico]", "", ""]
    return "\n".join(lines) + f"Usuário: {text}"


async def process_message(
    msg: IncomingMessage,
    *,
    api_base_url: str,
    transport=None,
    invite_link: Callable[[str], str] | None = None,
) -> list[OutgoingMessage]:
    who = f"{msg.channel}:{msg.external_user_id}"
    if not limiter.allow(who):
        logger.warning("[%s] Rate limit atingido", who)
        return _reply(msg, RATE_LIMIT_REPLY)

    try:
        db = get_service_supabase()
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        history = get_history(db, user["id"])

        alerts: list[str] = []
        tools = build_tools(
            user_token=generate_user_token(user["id"]),
            api_base_url=api_base_url,
            transport=transport,
            alert_sink=alerts,
            invite_link=invite_link,
        )
        logger.info("[%s] Mensagem recebida: %s", who, msg.text[:80])
        response = await create_agent(tools).arun(_with_history(history[-10:], msg.text))
        reply = response.content if hasattr(response, "content") else str(response)

        leaked = await resolve_leaked_tool_call(reply, tools)
        if leaked is not None:
            logger.warning("[%s] Tool call vazada como texto pelo modelo, executada manualmente", who)
            reply = leaked
        elif is_raw_provider_error(reply):
            logger.warning("[%s] Erro bruto do provedor vazou na resposta, usando fallback", who)
            reply = FALLBACK_REPLY

        history += [{"role": "user", "content": msg.text}, {"role": "assistant", "content": reply}]
        save_history(db, user["id"], history)
    except Exception:
        logger.exception("[%s] Falha ao processar mensagem", who)
        return _reply(msg, FALLBACK_REPLY)

    logger.info("[%s] Resposta: %s", who, reply[:120])
    return _reply(msg, reply) + [OutgoingMessage(chat_id=msg.chat_id, text=a) for a in alerts]


def process_start(msg: IncomingMessage, code: str | None) -> list[OutgoingMessage]:
    db = get_service_supabase()
    if code and code.startswith(JOIN_PREFIX):
        return _reply(msg, _join(db, msg, code[len(JOIN_PREFIX):]))
    if code:
        return _reply(msg, _link(db, msg, code))

    name = msg.display_name or "usuário"
    try:
        _, is_new = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
    except Exception:
        logger.exception("Falha ao registrar %s:%s", msg.channel, msg.external_user_id)
        return _reply(msg, "Não foi possível registrar seu acesso. Por favor, tente novamente.")

    if is_new:
        return _reply(msg, (
            f"Olá, {name}. Bem-vindo ao Assistente Financeiro.\n\n"
            "Para começar, informe suas transações em linguagem natural.\n"
            "Exemplo: 'Gastei R$ 50,00 no mercado hoje'\n\n"
            "Use /ajuda para ver todos os comandos disponíveis."
        ))
    return _reply(msg, (
        f"Bem-vindo de volta, {name}.\n\n"
        "Estou pronto para auxiliá-lo no controle financeiro.\n"
        "Use /ajuda para ver os comandos disponíveis."
    ))


def _link(db, msg: IncomingMessage, code: str) -> str:
    try:
        link_identity(db, code, msg.channel, msg.external_user_id)
    except InvalidLinkCode:
        return "Não foi possível vincular sua conta: código inválido ou expirado."
    except LinkConflict:
        return (
            "Não foi possível vincular: esta conta e a conta do painel já participam de grupos "
            "financeiros diferentes, e não é possível juntar os dois."
        )
    except Exception:
        logger.exception("Falha inesperada ao vincular %s:%s", msg.channel, msg.external_user_id)
        return "Não foi possível vincular sua conta agora. Tente novamente em instantes."
    return (
        "Conta vinculada com sucesso.\n\n"
        "Suas transações e limites agora são os mesmos do painel web."
    )


def _join(db, msg: IncomingMessage, token: str) -> str:
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group_id = accept_invite(db, token, user["id"])
    except InviteNotFound:
        return "Convite inválido, expirado ou já utilizado. Peça um novo link a quem convidou você."
    except AlreadyInGroup:
        return "Você já participa de um grupo financeiro e não pode entrar em outro."
    except Exception:
        logger.exception("Falha ao entrar no grupo %s:%s", msg.channel, msg.external_user_id)
        return "Não foi possível entrar no grupo agora. Tente novamente em instantes."
    return (
        f"Você entrou no grupo {group_name(db, group_id)}.\n\n"
        "Agora é só me contar seus gastos e receitas, por exemplo: 'Gastei R$ 50,00 no mercado'.\n"
        "Use /ajuda para ver tudo o que posso fazer."
    )


def invite_command(msg: IncomingMessage, invite_link: Callable[[str], str]) -> list[OutgoingMessage]:
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group_id = find_user_group(db, user["id"])
        if group_id is None:
            return _reply(msg, (
                "Você ainda não tem um grupo financeiro. "
                "Diga 'criar grupo' para criar um e depois use /convidar."
            ))
        invite = create_invite(db, group_id, user["id"])
    except Exception:
        logger.exception("Falha ao gerar convite %s:%s", msg.channel, msg.external_user_id)
        return _reply(msg, "Não foi possível gerar o convite agora. Tente novamente em instantes.")
    return _reply(msg, (
        "Envie este link ao familiar (uso único, válido por 7 dias):\n"
        f"{invite_link(invite['token'])}"
    ))


def help_message(msg: IncomingMessage) -> list[OutgoingMessage]:
    return _reply(msg, HELP_TEXT)
