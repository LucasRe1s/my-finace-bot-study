# -*- coding: utf-8 -*-
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from agent.bot import create_agent
from agent.history import get_history, save_history
from agent.tools import build_tools
from app.database import get_supabase


async def _get_or_create_user(db, telegram_id: int, first_name: str) -> dict | None:
    try:
        result = (
            db.table("users")
            .select("*")
            .eq("telegram_id", telegram_id)
            .single()
            .execute()
        )
        if result.data:
            return result.data
    except Exception:
        pass
    # User not found — create it
    insert_result = (
        db.table("users")
        .insert({"telegram_id": telegram_id, "name": first_name})
        .execute()
    )
    if not insert_result.data:
        return None
    return insert_result.data[0]


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    first_name = update.effective_user.first_name or "usuário"
    db = get_supabase()

    user = await _get_or_create_user(db, telegram_id, first_name)

    if user:
        msg = (
            f"Bem-vindo de volta, {first_name}.\n\n"
            "Estou pronto para auxiliá-lo no controle financeiro.\n"
            "Use /ajuda para ver os comandos disponíveis."
        )
    else:
        msg = (
            f"Olá, {first_name}. Bem-vindo ao Assistente Financeiro.\n\n"
            "Para começar, informe suas transações em linguagem natural.\n"
            "Exemplo: 'Gastei R$ 50,00 no mercado hoje'\n\n"
            "Use /ajuda para ver todos os comandos disponíveis."
        )

    await update.message.reply_text(msg)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "Comandos disponíveis:\n\n"
        "/start -- Iniciar ou reiniciar o assistente\n"
        "/ajuda -- Exibir esta mensagem\n\n"
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

    user = await _get_or_create_user(db, telegram_id, update.effective_user.first_name or "")
    if not user:
        await update.message.reply_text(
            "Usuário não encontrado. Por favor, use /start para se registrar."
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    history = get_history(db, user["id"])
    recent_history = history[-10:]  # ensure max 10 messages in context

    tools = build_tools(
        user_token=context.bot_data.get("service_token", ""),
        api_base_url=context.bot_data.get("api_base_url", "http://localhost:8000"),
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
    response = agent.run(full_message)
    bot_reply = response.content if hasattr(response, "content") else str(response)

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})
    save_history(db, user["id"], history)

    await update.message.reply_text(bot_reply)
