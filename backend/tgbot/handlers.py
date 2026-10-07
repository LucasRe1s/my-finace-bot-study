# -*- coding: utf-8 -*-
"""Adaptador Telegram: converte Update em IncomingMessage, chama o nucleo e
envia as respostas. Sem regra de negocio aqui."""
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.config import settings
from core.conversation import help_message, invite_command, process_message, process_start
from core.messages import IncomingMessage, OutgoingMessage


def _incoming(update: Update) -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        external_user_id=str(update.effective_user.id),
        display_name=update.effective_user.first_name or "",
        chat_id=str(update.effective_chat.id),
        text=update.message.text or "",
    )


async def _send(context: ContextTypes.DEFAULT_TYPE, outgoing: list[OutgoingMessage]) -> None:
    for out in outgoing:
        await context.bot.send_message(chat_id=int(out.chat_id), text=out.text)


def _invite_link(context: ContextTypes.DEFAULT_TYPE):
    username = context.bot.username
    return lambda token: f"https://t.me/{username}?start=join_{token}"


async def handle_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, invite_command(_incoming(update), _invite_link(context)))


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = context.args[0] if context.args else None
    await _send(context, process_start(_incoming(update), code))


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, help_message(_incoming(update)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    outgoing = await process_message(
        _incoming(update),
        api_base_url=context.bot_data.get("api_base_url", settings.api_base_url),
        transport=context.bot_data.get("api_transport"),
        invite_link=_invite_link(context),
    )
    await _send(context, outgoing)
