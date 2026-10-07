from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.messages import IncomingMessage, OutgoingMessage
from wabot import dispatch
from wabot.dispatch import UNSUPPORTED_REPLY, handle_event, invite_link, route_text
from wabot.parse import WhatsAppEvent


def _msg(text):
    return IncomingMessage(channel="whatsapp", external_user_id="5511", display_name="Ana", chat_id="5511", text=text, message_id="wamid.1")


def test_invite_link_uses_wa_me_with_prefilled_text():
    assert invite_link("5511999990000")("abc-1") == "https://wa.me/5511999990000?text=join_abc-1"


@pytest.mark.asyncio
@pytest.mark.parametrize("text,code", [
    ("join_abc-123", "join_abc-123"),
    ("/start ABC12345", "ABC12345"),
    ("/START abc12345", "abc12345"),
    ("/start", None),
    ("start", None),
])
async def test_start_and_join_go_to_process_start(text, code):
    with patch.object(dispatch, "process_start", return_value=[OutgoingMessage("5511", "ok")]) as start:
        out = await route_text(_msg(text), api_base_url="http://internal", transport=None)
    assert start.call_args.args[1] == code
    assert out[0].text == "ok"


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["/ajuda", "ajuda", "Ajuda"])
async def test_help(text):
    out = await route_text(_msg(text), api_base_url="http://internal", transport=None)
    assert "/convidar" in out[0].text and "/vincular" not in out[0].text


@pytest.mark.asyncio
async def test_invite_uses_whatsapp_link(monkeypatch):
    monkeypatch.setattr(dispatch.settings, "whatsapp_number", "5511999990000")
    with patch.object(dispatch, "invite_command", return_value=[]) as cmd:
        await route_text(_msg("/convidar"), api_base_url="http://internal", transport=None)
    assert cmd.call_args.args[1]("t") == "https://wa.me/5511999990000?text=join_t"


@pytest.mark.asyncio
async def test_free_text_goes_to_conversation(monkeypatch):
    monkeypatch.setattr(dispatch.settings, "whatsapp_number", "5511999990000")
    process = AsyncMock(return_value=[OutgoingMessage("5511", "Confirma?")])
    with patch.object(dispatch, "process_message", process):
        out = await route_text(_msg("gastei 50 no mercado"), api_base_url="http://internal", transport="t")
    assert out[0].text == "Confirma?"
    kwargs = process.call_args.kwargs
    assert kwargs["api_base_url"] == "http://internal" and kwargs["transport"] == "t"
    assert kwargs["invite_link"]("x").startswith("https://wa.me/5511999990000")


@pytest.mark.asyncio
async def test_handle_event_routes_by_kind_and_sends():
    client = MagicMock()
    client.send = AsyncMock()

    await handle_event(WhatsAppEvent("unsupported", _msg(""), "wamid.1"), client=client, api_base_url="", transport=None)
    assert client.send.call_args.args[0] == [OutgoingMessage("5511", UNSUPPORTED_REPLY)]

    with patch.object(dispatch, "process_button", return_value=[OutgoingMessage("5511", "aprovado")]) as button:
        await handle_event(WhatsAppEvent("button", _msg("approve:u1"), "wamid.2"), client=client, api_base_url="", transport=None)
    button.assert_called_once()
    assert client.send.call_args.args[0][0].text == "aprovado"
