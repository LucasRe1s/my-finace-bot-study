import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_start_command_registers_new_user():
    from tgbot.handlers import handle_start, _get_or_create_user

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Lucas"
    update.message.reply_text = AsyncMock()

    context = MagicMock()

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

    with patch("tgbot.handlers.get_supabase", return_value=mock_db):
        with patch("tgbot.handlers._get_or_create_user", return_value=({}, True)):
            await handle_start(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Lucas" in call_args or "bem-vindo" in call_args.lower()


@pytest.mark.asyncio
async def test_handle_message_calls_agent():
    from tgbot.handlers import handle_message

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.text = "Qual meu saldo este mes?"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()

    context = MagicMock()
    context.bot_data = {"service_token": "", "api_base_url": "http://localhost:8000"}

    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Resumo financeiro de junho..."
    mock_agent.run = MagicMock(return_value=mock_response)

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "user-uuid", "telegram_id": 123456789
    }

    with (
        patch("tgbot.handlers.get_supabase", return_value=mock_db),
        patch("tgbot.handlers._get_or_create_user", return_value=({"id": "user-uuid", "telegram_id": 123456789}, False)),
        patch("tgbot.handlers.create_agent", return_value=mock_agent),
        patch("tgbot.handlers.get_history", return_value=[]),
        patch("tgbot.handlers.save_history", return_value=None),
        patch("tgbot.handlers.build_tools", return_value=[]),
    ):
        await handle_message(update, context)

    update.message.reply_text.assert_called_once()
