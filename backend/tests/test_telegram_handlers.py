from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.messages import IncomingMessage, OutgoingMessage


def _update(text="oi", user_id=555, chat_id=555, first_name="Ana"):
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_user.first_name = first_name
    update.effective_chat.id = chat_id
    update.effective_chat.send_action = AsyncMock()
    update.message.text = text
    return update


def _context(args=None):
    context = MagicMock()
    context.args = args or []
    context.bot.send_message = AsyncMock()
    context.bot_data = {"api_base_url": "http://internal", "api_transport": "transport"}
    return context


@pytest.mark.asyncio
async def test_message_is_converted_and_replies_are_sent():
    from tgbot.handlers import handle_message

    update, context = _update(text="Qual meu saldo?"), _context()
    replies = [OutgoingMessage("555", "Saldo"), OutgoingMessage("555", "ALERTA")]
    with patch("tgbot.handlers.process_message", AsyncMock(return_value=replies)) as process:
        await handle_message(update, context)

    msg = process.call_args.args[0]
    assert msg == IncomingMessage(channel="telegram", external_user_id="555", display_name="Ana", chat_id="555", text="Qual meu saldo?")
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
