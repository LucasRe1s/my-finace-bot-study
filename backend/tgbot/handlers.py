# -*- coding: utf-8 -*-
"""Adaptador Telegram: converte Update em IncomingMessage, chama o nucleo e
envia as respostas. Sem regra de negocio aqui."""
import logging
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.config import settings
from core.conversation import help_message, invite_command, process_message, process_start
from core.group_chat import bind_command, chat_migrated, group_welcome, process_button, unbind_command
from core.messages import IncomingMessage, OutgoingMessage
from core.transcription import transcribe_audio

logger = logging.getLogger("bot")

CHANNEL = "telegram"
# Limite de download de arquivos da Bot API.
MAX_AUDIO_BYTES = 20 * 1024 * 1024


def _is_group(update: Update) -> bool:
    return update.effective_chat.type != "private"


def _replied_to_bot(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    reply = update.message.reply_to_message
    return reply is not None and reply.from_user.id == context.bot.id


def _incoming(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str | None = None, addressed: bool | None = None) -> IncomingMessage:
    message = update.message
    raw = message.text if text is None else text
    raw = raw or ""
    group = _is_group(update)
    if group and addressed is None:
        mention = f"@{context.bot.username}"
        replied = _replied_to_bot(update, context)
        mentioned = mention.lower() in raw.lower()
        addressed = replied or mentioned
        raw = re.sub(re.escape(mention), "", raw, flags=re.IGNORECASE).strip()
    return IncomingMessage(
        channel=CHANNEL,
        external_user_id=str(update.effective_user.id),
        display_name=update.effective_user.first_name or "",
        chat_id=str(update.effective_chat.id),
        text=raw,
        chat_type="group" if group else "private",
        addressed=True if addressed is None else addressed,
        message_id=str(message.message_id),
    )


async def _send(context: ContextTypes.DEFAULT_TYPE, outgoing: list[OutgoingMessage]) -> None:
    for out in outgoing:
        kwargs = {"chat_id": int(out.chat_id), "text": out.text}
        if out.reply_to:
            # allow_sending_without_reply: se a mensagem original sumiu, envia mesmo assim.
            kwargs["reply_parameters"] = ReplyParameters(message_id=int(out.reply_to), allow_sending_without_reply=True)
        if out.buttons:
            kwargs["reply_markup"] = InlineKeyboardMarkup(
                [[InlineKeyboardButton(b.label, callback_data=b.action) for b in out.buttons]]
            )
        await context.bot.send_message(**kwargs)


def _invite_link(context: ContextTypes.DEFAULT_TYPE):
    username = context.bot.username
    return lambda token: f"https://t.me/{username}?start=join_{token}"


async def _converse(update: Update, context: ContextTypes.DEFAULT_TYPE, msg: IncomingMessage) -> None:
    if msg.chat_type == "group" and not msg.addressed:
        # Conversa da familia que nao e com o bot. O nucleo tambem ignora;
        # aqui evita ate o "digitando...".
        return
    await update.effective_chat.send_action(ChatAction.TYPING)
    outgoing = await process_message(
        msg,
        api_base_url=context.bot_data.get("api_base_url", settings.api_base_url),
        transport=context.bot_data.get("api_transport"),
        invite_link=_invite_link(context),
    )
    await _send(context, outgoing)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _converse(update, context, _incoming(update, context))


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Audio vira texto (Whisper) e segue o mesmo fluxo de uma mensagem digitada.
    Em grupo nao da para mencionar o bot por voz: so responde a quem respondeu ao bot."""
    group = _is_group(update)
    if group and not _replied_to_bot(update, context):
        return

    message = update.message
    reply_to = str(message.message_id) if group else None

    async def reply(text: str) -> None:
        await _send(context, [OutgoingMessage(str(update.effective_chat.id), text, reply_to=reply_to)])

    media = message.voice or message.audio
    if media.file_size and media.file_size > MAX_AUDIO_BYTES:
        await reply("O áudio é muito longo para ser processado. Envie uma gravação mais curta.")
        return

    await update.effective_chat.send_action(ChatAction.TYPING)
    try:
        tg_file = await media.get_file()
        text = await transcribe_audio(bytes(await tg_file.download_as_bytearray()))
    except Exception:
        logger.exception("Falha ao transcrever audio do chat %s", update.effective_chat.id)
        await reply("Não foi possível processar o áudio agora. Tente novamente ou envie por texto.")
        return

    if not text:
        await reply("Não consegui entender o áudio. Pode repetir ou enviar por texto?")
        return

    await _converse(update, context, _incoming(update, context, text=text, addressed=True))


async def handle_f(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _converse(update, context, _incoming(update, context, text=" ".join(context.args or []), addressed=True))


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = context.args[0] if context.args else None
    await _send(context, process_start(_incoming(update, context, addressed=True), code))


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, help_message(_incoming(update, context, addressed=True)))


async def handle_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, invite_command(_incoming(update, context, addressed=True), _invite_link(context)))


async def handle_bind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, bind_command(_incoming(update, context, addressed=True)))


async def handle_unbind(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, unbind_command(_incoming(update, context, addressed=True)))


async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    chat = query.message.chat
    msg = IncomingMessage(
        channel=CHANNEL,
        external_user_id=str(query.from_user.id),
        display_name=query.from_user.first_name or "",
        chat_id=str(chat.id),
        text=query.data or "",
        chat_type="group" if chat.type != "private" else "private",
        message_id=str(query.message.message_id),
    )
    await _send(context, process_button(msg))


async def handle_new_members(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if any(member.id == context.bot.id for member in update.message.new_chat_members):
        await _send(context, group_welcome(_incoming(update, context, addressed=True)))


async def handle_migration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    new_chat_id = update.message.migrate_to_chat_id
    if new_chat_id:
        chat_migrated(CHANNEL, str(update.effective_chat.id), str(new_chat_id))
