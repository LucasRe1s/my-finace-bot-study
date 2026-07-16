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
    context.args = []

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = None
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

    with patch("tgbot.handlers.get_supabase", return_value=mock_db):
        with patch("tgbot.handlers._get_or_create_user", return_value=({"id": "user-uuid", "telegram_id": 123456789}, True)):
            await handle_start(update, context)

    update.message.reply_text.assert_called_once()
    call_args = update.message.reply_text.call_args[0][0]
    assert "Lucas" in call_args or "bem-vindo" in call_args.lower()


@pytest.mark.asyncio
async def test_start_command_with_link_code_calls_link_endpoint():
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Lucas"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["ABC12345"]
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        await handle_start(update, context)

    sent_json = mock_client.return_value.__aenter__.return_value.post.call_args.kwargs["json"]
    assert sent_json == {"code": "ABC12345", "telegram_id": 123456789}
    reply = update.message.reply_text.call_args[0][0]
    assert "vinculado" in reply.lower()


@pytest.mark.asyncio
async def test_start_command_with_invalid_code_shows_code_error():
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Lucas"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["EXPIRADO"]
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        await handle_start(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "código inválido ou expirado" in reply.lower()


@pytest.mark.asyncio
async def test_start_command_with_server_error_shows_generic_retry():
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Lucas"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["ABC12345"]
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        await handle_start(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "código" not in reply.lower()
    assert "tente novamente" in reply.lower()


@pytest.mark.asyncio
async def test_handle_message_replaces_raw_provider_error_with_fallback():
    from tgbot.handlers import handle_message

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.text = "sim"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()

    context = MagicMock()
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    raw_error = (
        '{"error":{"message":"Failed to call a function.","type":"invalid_request_error",'
        '"code":"tool_use_failed","failed_generation":"..."}}'
    )
    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.content = raw_error
    mock_agent.arun = AsyncMock(return_value=mock_response)

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

    reply = update.message.reply_text.call_args[0][0]
    assert "tool_use_failed" not in reply
    assert "pode tentar novamente" in reply.lower()


@pytest.mark.asyncio
async def test_handle_message_calls_agent():
    from tgbot.handlers import handle_message

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.text = "Qual meu saldo este mes?"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()

    context = MagicMock()
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "Resumo financeiro de junho..."
    mock_agent.arun = AsyncMock(return_value=mock_response)

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


@pytest.mark.asyncio
async def test_handle_message_resolves_leaked_tool_call():
    from tgbot.handlers import handle_message

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.text = "sim, confirmo"
    update.message.reply_text = AsyncMock()
    update.message.chat.send_action = AsyncMock()

    context = MagicMock()
    context.bot_data = {"api_base_url": "http://localhost:8000"}

    leaked_text = (
        '<function=registrar_transacao>{"type": "income", "amount": 1180.00, '
        '"category": "Outros", "date": "", "description": "crédito na conta"}</function>'
    )
    mock_agent = MagicMock()
    mock_response = MagicMock()
    mock_response.content = leaked_text
    mock_agent.arun = AsyncMock(return_value=mock_response)

    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
        "id": "user-uuid", "telegram_id": 123456789
    }

    fake_tool = AsyncMock(return_value="Transação registrada com sucesso. Receita de R$ 1.180,00 em Outros na data 2026-07-16.")
    fake_tool.__name__ = "registrar_transacao"

    saved_history = {}

    def _capture_save(db, user_id, history):
        saved_history["history"] = history

    with (
        patch("tgbot.handlers.get_supabase", return_value=mock_db),
        patch("tgbot.handlers._get_or_create_user", return_value=({"id": "user-uuid", "telegram_id": 123456789}, False)),
        patch("tgbot.handlers.create_agent", return_value=mock_agent),
        patch("tgbot.handlers.get_history", return_value=[]),
        patch("tgbot.handlers.save_history", side_effect=_capture_save),
        patch("tgbot.handlers.build_tools", return_value=[fake_tool]),
    ):
        await handle_message(update, context)

    fake_tool.assert_called_once()
    reply_sent = update.message.reply_text.call_args[0][0]
    assert "<function=" not in reply_sent
    assert "R$ 1.180,00" in reply_sent
    assert "<function=" not in saved_history["history"][-1]["content"]
