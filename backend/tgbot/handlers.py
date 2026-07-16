# -*- coding: utf-8 -*-
import jwt
import logging
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

logger = logging.getLogger("bot")

from agent.bot import create_agent
from agent.history import get_history, save_history
from agent.tools import build_tools
from app.config import settings
from app.database import get_supabase


def _generate_user_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


async def _get_or_create_user(db, telegram_id: int, first_name: str) -> tuple[dict | None, bool]:
    result = (
        db.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if result and result.data:
        return result.data, False
    logger.info("Novo usuário Telegram %s (%s) — criando registro", telegram_id, first_name)
    insert_result = (
        db.table("users")
        .insert({"telegram_id": telegram_id, "name": first_name})
        .execute()
    )
    if not insert_result.data:
        return None, False
    return insert_result.data[0], True


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    first_name = update.effective_user.first_name or "usuário"
    db = get_supabase()

    user, is_new = await _get_or_create_user(db, telegram_id, first_name)

    if user and is_new:
        msg = (
            f"Olá, {first_name}. Bem-vindo ao Assistente Financeiro.\n\n"
            "Para começar, informe suas transações em linguagem natural.\n"
            "Exemplo: 'Gastei R$ 50,00 no mercado hoje'\n\n"
            "Use /ajuda para ver todos os comandos disponíveis."
        )
    elif user and not is_new:
        msg = (
            f"Bem-vindo de volta, {first_name}.\n\n"
            "Estou pronto para auxiliá-lo no controle financeiro.\n"
            "Use /ajuda para ver os comandos disponíveis."
        )
    else:
        msg = "Não foi possível registrar seu acesso. Por favor, tente novamente."

    await update.message.reply_text(msg)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "Comandos disponíveis:\n\n"
        "/start — Iniciar ou reiniciar o assistente\n"
        "/ajuda — Exibir esta mensagem\n\n"
        "O que posso fazer por você:\n"
        "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')\n"
        "- Consultar saldo do mês ('Qual meu saldo?')\n"
        "- Ver extrato ('Mostre meus gastos de junho')\n"
        "- Resumo por categoria ('Quanto gastei com alimentação?')\n"
        "- Definir limites ('Limite de R$ 500 para Alimentação')\n"
        "- Ver limites ('Quais são meus limites?')"
    )
    await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user_message = update.message.text
    db = get_supabase()

    user, _ = await _get_or_create_user(db, telegram_id, update.effective_user.first_name or "")
    if not user:
        await update.message.reply_text(
            "Usuário não encontrado. Por favor, use /start para se registrar."
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)
    logger.info("[%s] Mensagem recebida: %s", telegram_id, user_message[:80])

    user_token = _generate_user_token(user["id"])

    history = get_history(db, user["id"])
    recent_history = history[-10:]

    tools = build_tools(
        user_token=user_token,
        api_base_url=context.bot_data.get("api_base_url", "http://localhost:8000"),
        bot=context.bot,
        telegram_id=telegram_id,
    )
    agent = create_agent(tools)

    history_context = ""
    if recent_history:
        history_context = "\n\n[Histórico recente da conversa:]\n"
        for msg in recent_history:
            role = "Usuário" if msg["role"] == "user" else "Assistente"
            history_context += f"{role}: {msg['content']}\n"
        history_context += "[Fim do histórico]\n\n"

    full_message = f"{history_context}Usuário: {user_message}"
    logger.info("[%s] Chamando agente Groq...", telegram_id)
    response = await agent.arun(full_message)
    bot_reply = response.content if hasattr(response, "content") else str(response)
    logger.info("[%s] Resposta: %s", telegram_id, bot_reply[:120])

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})
    save_history(db, user["id"], history)

    await update.message.reply_text(bot_reply)
