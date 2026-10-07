from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.messages import IncomingMessage, OutgoingMessage


def _update(text="oi", user_id=555, chat_id=555, first_name="Ana", chat_type="private", message_id=7, reply_to_bot=False):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = first_name
    update.effective_chat.id = chat_id
    update.effective_chat.type = chat_type
    update.effective_chat.send_action = AsyncMock()
    update.message.text = text
    update.message.message_id = message_id
    if reply_to_bot:
        update.message.reply_to_message.from_user.id = 999
    else:
        update.message.reply_to_message = None
    return update


def _context(args=None):
    context = MagicMock()
    context.args = args or []
    context.bot.send_message = AsyncMock()
    context.bot_data = {"api_base_url": "http://internal", "api_transport": "transport"}
    context.bot.id = 999
    context.bot.username = "finncyBot"
    return context


@pytest.mark.asyncio
async def test_message_is_converted_and_replies_are_sent():
    from tgbot.handlers import handle_message

    update, context = _update(text="Qual meu saldo?"), _context()
    replies = [OutgoingMessage("555", "Saldo"), OutgoingMessage("555", "ALERTA")]
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=replies)) as process:
        await handle_message(update, context)

    msg = process.call_args.args[0]
    assert msg == IncomingMessage(channel="telegram", external_user_id="555", display_name="Ana", chat_id="555", text="Qual meu saldo?", message_id="7")
    kwargs = process.call_args.kwargs
    assert kwargs["api_base_url"] == "http://internal" and kwargs["transport"] == "transport"
    assert kwargs["invite_link"]("abc").endswith("?start=join_abc")
    sent = [c.kwargs for c in context.bot.send_message.call_args_list]
    assert sent == [{"chat_id": 555, "text": "Saldo"}, {"chat_id": 555, "text": "ALERTA"}]


@pytest.mark.asyncio
async def test_start_passes_code():
    from tgbot.handlers import handle_start

    update, context = _update(text="/start ABC12345"), _context(args=["ABC12345"])
    with patch("tgbot.handlers.process_start", return_value=[OutgoingMessage("555", "ok")]) as start:
        await handle_start(update, context)

    assert start.call_args.args[1] == "ABC12345"
    context.bot.send_message.assert_awaited_once_with(chat_id=555, text="ok")


@pytest.mark.asyncio
async def test_help_sends_help_text():
    from core.conversation import HELP_TEXT
    from tgbot.handlers import handle_help

    update, context = _update(text="/ajuda"), _context()
    await handle_help(update, context)
    context.bot.send_message.assert_awaited_once_with(chat_id=555, text=HELP_TEXT)


@pytest.mark.asyncio
async def test_invite_command_uses_telegram_deep_link():
    from tgbot.handlers import handle_invite

    update, context = _update(text="/convidar"), _context()
    context.bot.username = "finncyBot"
    with patch("tgbot.handlers.invite_command", return_value=[OutgoingMessage("555", "link")]) as cmd:
        await handle_invite(update, context)

    link = cmd.call_args.args[1]
    assert link("abc") == "https://t.me/finncyBot?start=join_abc"
    context.bot.send_message.assert_awaited_once_with(chat_id=555, text="link")


@pytest.mark.asyncio
async def test_group_message_without_mention_is_not_addressed():
    from tgbot.handlers import handle_message

    update, context = _update(text="alguém viu meu guarda-chuva?", chat_id=-100, chat_type="group"), _context()
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=[])) as process:
        await handle_message(update, context)

    process.assert_not_called()
    update.effective_chat.send_action.assert_not_called()


@pytest.mark.asyncio
async def test_group_mention_is_addressed_and_stripped():
    from tgbot.handlers import handle_message

    update, context = _update(text="@FinncyBot gastei 50", chat_id=-100, chat_type="supergroup"), _context()
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=[])) as process:
        await handle_message(update, context)

    msg = process.call_args.args[0]
    assert (msg.chat_type, msg.addressed, msg.text, msg.message_id) == ("group", True, "gastei 50", "7")


@pytest.mark.asyncio
async def test_group_reply_to_bot_is_addressed():
    from tgbot.handlers import handle_message

    update, context = _update(text="sim", chat_id=-100, chat_type="group", reply_to_bot=True), _context()
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=[])) as process:
        await handle_message(update, context)

    assert process.call_args.args[0].addressed is True


@pytest.mark.asyncio
async def test_f_command_sends_text_after_command():
    from tgbot.handlers import handle_f

    update, context = _update(text="/f@finncyBot gastei 50", chat_id=-100, chat_type="group"), _context(args=["gastei", "50"])
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=[])) as process:
        await handle_f(update, context)

    msg = process.call_args.args[0]
    assert (msg.text, msg.addressed) == ("gastei 50", True)


@pytest.mark.asyncio
async def test_reply_and_buttons_are_rendered():
    from core.messages import Button
    from telegram import InlineKeyboardMarkup
    from tgbot.handlers import handle_message

    update, context = _update(text="@finncyBot oi", chat_id=-100, chat_type="group"), _context()
    out = [OutgoingMessage("-100", "Aprovar?", reply_to="7", buttons=(Button("Aprovar Bia", "approve:bia"),))]
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=out)):
        await handle_message(update, context)

    kwargs = context.bot.send_message.call_args.kwargs
    assert kwargs["chat_id"] == -100
    assert kwargs["reply_parameters"].message_id == 7
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].callback_data == "approve:bia"


@pytest.mark.asyncio
async def test_button_click_goes_to_core():
    from tgbot.handlers import handle_button

    update, context = MagicMock(), _context()
    query = update.callback_query
    query.answer = AsyncMock()
    query.data = "approve:bia"
    query.from_user.id = 1
    query.from_user.first_name = "Ana"
    query.message.chat.id = -100
    query.message.chat.type = "group"
    query.message.message_id = 50
    with patch("tgbot.handlers.process_button", return_value=[OutgoingMessage("-100", "Bia agora faz parte")]) as button:
        await handle_button(update, context)

    query.answer.assert_awaited_once()
    msg = button.call_args.args[0]
    assert (msg.text, msg.external_user_id, msg.chat_id, msg.chat_type) == ("approve:bia", "1", "-100", "group")
    context.bot.send_message.assert_awaited_once()


@pytest.mark.asyncio
async def test_bot_added_to_group_sends_welcome():
    from core.group_chat import GROUP_WELCOME
    from tgbot.handlers import handle_new_members

    update, context = _update(text=None, chat_id=-100, chat_type="group"), _context()
    bot_member = MagicMock(id=999)
    update.message.new_chat_members = [MagicMock(id=1), bot_member]
    await handle_new_members(update, context)
    context.bot.send_message.assert_awaited_once_with(chat_id=-100, text=GROUP_WELCOME)


@pytest.mark.asyncio
async def test_migration_moves_binding():
    from tgbot.handlers import handle_migration

    update, context = _update(text=None, chat_id=-100, chat_type="group"), _context()
    update.message.migrate_to_chat_id = -100999
    with patch("tgbot.handlers.chat_migrated") as migrated:
        await handle_migration(update, context)
    migrated.assert_called_once_with("telegram", "-100", "-100999")
