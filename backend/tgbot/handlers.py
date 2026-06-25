# -*- coding: utf-8 -*-
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from agent.bot import create_agent
from agent.history import get_history, save_history
from agent.tools import build_tools
from app.database import get_supabase


async def _get_or_create_user(db, telegram_id: int, first_name: str) -> dict | None:
    result = (
        db.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    )
    return result.data


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    first_name = update.effective_user.first_name or "usuario"
    db = get_supabase()

    user = await _get_or_create_user(db, telegram_id, first_name)

    if user:
        msg = (
            f"Bem-vindo de volta, {first_name}.\n\n"
            "Estou pronto para auxiliá-lo no controle financeiro.\n"
            "Use /ajuda para ver os comandos disponiveis."
        )
    else:
        msg = (
            f"Ola, {first_name}. Bem-vindo ao Assistente Financeiro.\n\n"
            "Para comecar, informe suas transacoes em linguagem natural.\n"
            "Exemplo: 'Gastei R$ 50,00 no mercado hoje'\n\n"
            "Use /ajuda para ver todos os comandos disponiveis."
        )

    await update.message.reply_text(msg)


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    msg = (
        "Comandos disponiveis:\n\n"
        "/start -- Iniciar ou reiniciar o assistente\n"
        "/ajuda -- Exibir esta mensagem\n\n"
        "O que posso fazer por voce:\n"
        "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')\n"
        "- Consultar saldo do mes ('Qual meu saldo?')\n"
        "- Ver extrato ('Mostre meus gastos de junho')\n"
        "- Resumo por categoria ('Quanto gastei com alimentacao?')\n"
        "- Definir limites ('Limite de R$ 500 para Alimentacao')\n"
        "- Ver limites ('Quais sao meus limites?')"
    )
    await update.message.reply_text(msg)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    telegram_id = update.effective_user.id
    user_message = update.message.text
    db = get_supabase()

    user = await _get_or_create_user(db, telegram_id, update.effective_user.first_name or "")
    if not user:
        await update.message.reply_text(
            "Usuario nao encontrado. Por favor, use /start para se registrar."
        )
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    history = get_history(db, user["id"])

    tools = build_tools(
        user_token=context.bot_data.get("service_token", ""),
        api_base_url=context.bot_data.get("api_base_url", "http://localhost:8000"),
    )
    agent = create_agent(tools)

    history_context = ""
    if history:
        history_context = "\n\n[Historico recente da conversa:]\n"
        for msg in history:
            role = "Usuario" if msg["role"] == "user" else "Assistente"
            history_context += f"{role}: {msg['content']}\n"
        history_context += "[Fim do historico]\n\n"

    full_message = f"{history_context}Usuario: {user_message}"
    response = agent.run(full_message)
    bot_reply = response.content if hasattr(response, "content") else str(response)

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": bot_reply})
    save_history(db, user["id"], history)

    await update.message.reply_text(bot_reply)
