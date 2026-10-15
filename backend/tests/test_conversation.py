from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from core import conversation
from core.conversation import FALLBACK_REPLY, RATE_LIMIT_REPLY, invite_command, process_message, process_start
from core.messages import IncomingMessage, OutgoingMessage
from core.rate_limit import SlidingWindowLimiter
from tests.fakes import FakeSupabase

LINK = lambda token: f"https://t.me/finncyBot?start=join_{token}"  # noqa: E731
_FUTURE = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()

MSG = IncomingMessage(channel="telegram", external_user_id="555", display_name="Ana", chat_id="555", text="Qual meu saldo?")


@pytest.fixture(autouse=True)
def fresh_limiter(monkeypatch):
    monkeypatch.setattr(conversation, "limiter", SlidingWindowLimiter(max_events=30, window_seconds=600))


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(
        unique={"user_identities": [("channel", "external_id")]},
        defaults={"invites": lambda: {"token": str(uuid4()), "accepted_at": None, "expires_at": _FUTURE}},
    )
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


def _group_with_invite(db, token="tok"):
    db.tables["groups"] = [{"id": "g1", "name": "Família Silva"}]
    db.tables["invites"] = [{"id": "i1", "group_id": "g1", "token": token, "accepted_at": None, "expires_at": _FUTURE}]


def test_start_join_adds_new_user_to_group(db):
    _group_with_invite(db)

    out = process_start(MSG, "join_tok")

    assert "Família Silva" in out[0].text
    user_id = db.tables["user_identities"][0]["user_id"]
    assert db.tables["group_members"][0]["user_id"] == user_id


def test_start_join_with_used_invite(db):
    _group_with_invite(db)
    db.tables["invites"][0]["accepted_at"] = "2026-10-01T00:00:00+00:00"

    out = process_start(MSG, "join_tok")

    assert "inválido, expirado ou já utilizado" in out[0].text


def test_start_join_when_already_in_group(db):
    _group_with_invite(db)
    process_start(MSG, None)
    user_id = db.tables["user_identities"][0]["user_id"]
    db.tables["group_members"] = [{"id": "m", "group_id": "outro", "user_id": user_id, "role": "owner"}]

    out = process_start(MSG, "join_tok")

    assert "já participa de um grupo" in out[0].text


def test_invite_command_returns_link(db):
    process_start(MSG, None)
    user_id = db.tables["user_identities"][0]["user_id"]
    db.tables["group_members"] = [{"id": "m", "group_id": "g1", "user_id": user_id, "role": "owner"}]

    out = invite_command(MSG, LINK)

    token = db.tables["invites"][0]["token"]
    assert f"https://t.me/finncyBot?start=join_{token}" in out[0].text


def test_invite_command_without_group(db):
    out = invite_command(MSG, LINK)
    assert "ainda não tem um grupo" in out[0].text
    assert "invites" not in db.tables


@pytest.mark.asyncio
async def test_process_message_passes_invite_link_to_tools(db):
    captured = {}

    def fake_build_tools(**kwargs):
        captured.update(kwargs)
        return []

    with patch.object(conversation, "create_agent", return_value=_agent_replying("ok")), patch.object(conversation, "build_tools", side_effect=fake_build_tools):
        await process_message(MSG, api_base_url="http://internal", invite_link=LINK)

    assert captured["invite_link"] is LINK


def test_help_text_hides_telegram_group_commands_on_whatsapp():
    from core.conversation import HELP_TEXT, help_text

    assert HELP_TEXT == help_text("telegram")
    assert "/vincular" in help_text("telegram")
    whatsapp = help_text("whatsapp")
    assert "/vincular" not in whatsapp and "/f " not in whatsapp
    assert "/convidar" in whatsapp and "/ajuda" in whatsapp
