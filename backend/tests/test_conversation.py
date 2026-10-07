from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import conversation
from core.conversation import FALLBACK_REPLY, RATE_LIMIT_REPLY, process_message, process_start
from core.messages import IncomingMessage, OutgoingMessage
from core.rate_limit import SlidingWindowLimiter
from tests.fakes import FakeSupabase

MSG = IncomingMessage(channel="telegram", external_user_id="555", display_name="Ana", chat_id="555", text="Qual meu saldo?")


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.setattr(conversation, "limiter", SlidingWindowLimiter(max_events=30, window_seconds=600))


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(unique={"user_identities": [("channel", "external_id")]})
    monkeypatch.setattr(conversation, "get_service_supabase", lambda: fake)
    return fake


def _agent_replying(text):
    agent = MagicMock()
    agent.arun = AsyncMock(return_value=MagicMock(content=text))
    return agent


@pytest.mark.asyncio
async def test_replies_and_saves_history(db):
    with (
        patch.object(conversation, "create_agent", return_value=_agent_replying("Saldo: R$ 10,00")),
        patch.object(conversation, "build_tools", return_value=[]),
    ):
        out = await process_message(MSG, api_base_url="http://internal")

    assert out == [OutgoingMessage(chat_id="555", text="Saldo: R$ 10,00")]
    saved = db.tables["conversations"][0]["messages"]
    assert saved[-2:] == [
        {"role": "user", "content": "Qual meu saldo?"},
        {"role": "assistant", "content": "Saldo: R$ 10,00"},
    ]


@pytest.mark.asyncio
async def test_sends_history_to_agent(db):
    agent = _agent_replying("ok")
    with patch.object(conversation, "create_agent", return_value=agent), patch.object(conversation, "build_tools", return_value=[]):
        await process_message(MSG, api_base_url="http://internal")
        await process_message(MSG, api_base_url="http://internal")

    prompt = agent.arun.call_args_list[-1].args[0]
    assert "[Histórico recente da conversa:]" in prompt
    assert prompt.endswith("Usuário: Qual meu saldo?")


@pytest.mark.asyncio
async def test_limit_alerts_come_after_reply(db):
    def fake_build_tools(**kwargs):
        kwargs["alert_sink"].append("ALERTA: limite")
        return []

    with (
        patch.object(conversation, "create_agent", return_value=_agent_replying("Registrado.")),
        patch.object(conversation, "build_tools", side_effect=fake_build_tools),
    ):
        out = await process_message(MSG, api_base_url="http://internal")

    assert [o.text for o in out] == ["Registrado.", "ALERTA: limite"]


@pytest.mark.asyncio
async def test_raw_provider_error_becomes_fallback(db):
    raw = '{"error":{"code":"tool_use_failed","type":"invalid_request_error"}}'
    with patch.object(conversation, "create_agent", return_value=_agent_replying(raw)), patch.object(conversation, "build_tools", return_value=[]):
        out = await process_message(MSG, api_base_url="http://internal")
    assert out[0].text == FALLBACK_REPLY


@pytest.mark.asyncio
async def test_leaked_tool_call_is_executed(db):
    async def registrar_transacao(amount: float, type: str, category: str, description: str = "", date: str = None):
        return f"Transação registrada: {amount}"

    leaked = '<function=registrar_transacao>{"amount": 10, "type": "expense", "category": "Outros"}</function>'
    with (
        patch.object(conversation, "create_agent", return_value=_agent_replying(leaked)),
        patch.object(conversation, "build_tools", return_value=[registrar_transacao]),
    ):
        out = await process_message(MSG, api_base_url="http://internal")

    assert out[0].text == "Transação registrada: 10"
    assert db.tables["conversations"][0]["messages"][-1]["content"] == "Transação registrada: 10"


@pytest.mark.asyncio
async def test_unexpected_error_becomes_fallback(db):
    agent = MagicMock()
    agent.arun = AsyncMock(side_effect=RuntimeError("groq fora"))
    with patch.object(conversation, "create_agent", return_value=agent), patch.object(conversation, "build_tools", return_value=[]):
        out = await process_message(MSG, api_base_url="http://internal")
    assert out == [OutgoingMessage(chat_id="555", text=FALLBACK_REPLY)]


@pytest.mark.asyncio
async def test_rate_limit_blocks_before_calling_agent(db, monkeypatch):
    monkeypatch.setattr(conversation, "limiter", SlidingWindowLimiter(max_events=1, window_seconds=600))
    create_agent = MagicMock(return_value=_agent_replying("ok"))
    with patch.object(conversation, "create_agent", create_agent), patch.object(conversation, "build_tools", return_value=[]):
        await process_message(MSG, api_base_url="http://internal")
        out = await process_message(MSG, api_base_url="http://internal")

    assert out == [OutgoingMessage(chat_id="555", text=RATE_LIMIT_REPLY)]
    assert create_agent.call_count == 1


def test_start_without_code_welcomes_new_user(db):
    out = process_start(MSG, None)
    assert "Olá, Ana" in out[0].text


def test_start_with_code_links(db):
    with patch.object(conversation, "link_identity") as link:
        out = process_start(MSG, "ABC12345")
    link.assert_called_once_with(db, "ABC12345", "telegram", "555")
    assert "vinculada com sucesso" in out[0].text.lower()


def test_start_with_invalid_code(db):
    from app.services.identities import InvalidLinkCode

    with patch.object(conversation, "link_identity", side_effect=InvalidLinkCode()):
        out = process_start(MSG, "EXPIRADO")
    assert "código inválido ou expirado" in out[0].text.lower()


def test_start_with_conflicting_groups(db):
    from app.services.identities import LinkConflict

    with patch.object(conversation, "link_identity", side_effect=LinkConflict()):
        out = process_start(MSG, "ABC12345")
    assert "grupo" in out[0].text.lower()


def test_start_with_unexpected_error(db):
    with patch.object(conversation, "link_identity", side_effect=RuntimeError("db fora")):
        out = process_start(MSG, "ABC12345")
    assert "tente novamente" in out[0].text.lower()
