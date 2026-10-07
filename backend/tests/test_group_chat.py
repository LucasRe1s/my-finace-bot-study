from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core import conversation, group_chat
from core.conversation import process_message
from core.group_chat import (
    NOT_BOUND_REPLY,
    bind_command,
    chat_migrated,
    process_button,
    unbind_command,
)
from core.messages import Button, IncomingMessage
from core.rate_limit import SlidingWindowLimiter
from tests.fakes import FakeSupabase

CHAT = "-100"


def _msg(user="1", name="Ana", text="gastei 10", addressed=True, chat_type="group"):
    return IncomingMessage(
        channel="telegram", external_user_id=user, display_name=name, chat_id=CHAT,
        text=text, chat_type=chat_type, addressed=addressed, message_id="42",
    )


@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(unique={
        "user_identities": [("channel", "external_id")],
        "chat_bindings": [("channel", "chat_id"), ("group_id",)],
    })
    fake.tables["users"] = [{"id": "ana", "name": "Ana"}, {"id": "bia", "name": "Bia"}]
    fake.tables["user_identities"] = [
        {"id": "i1", "user_id": "ana", "channel": "telegram", "external_id": "1"},
        {"id": "i2", "user_id": "bia", "channel": "telegram", "external_id": "2"},
    ]
    fake.tables["groups"] = [{"id": "g1", "name": "Casa", "owner_id": "ana"}]
    fake.tables["group_members"] = [{"id": "m1", "group_id": "g1", "user_id": "ana", "role": "owner"}]
    for module in (conversation, group_chat):
        monkeypatch.setattr(module, "get_service_supabase", lambda: fake)
    monkeypatch.setattr(conversation, "limiter", SlidingWindowLimiter(max_events=30, window_seconds=600))
    return fake


def _bind(db):
    db.tables["chat_bindings"] = [{"id": "b1", "channel": "telegram", "chat_id": CHAT, "group_id": "g1"}]


def _agent(text="ok"):
    agent = MagicMock()
    agent.arun = AsyncMock(return_value=MagicMock(content=text))
    return agent


async def _run(msg, agent=None):
    with patch.object(conversation, "create_agent", return_value=agent or _agent()), patch.object(conversation, "build_tools", return_value=[]):
        return await process_message(msg, api_base_url="http://internal")


@pytest.mark.asyncio
async def test_ignores_group_message_not_addressed_to_bot(db):
    agent = _agent()
    assert await _run(_msg(addressed=False), agent) == []
    agent.arun.assert_not_called()


@pytest.mark.asyncio
async def test_unbound_chat_asks_owner_to_bind(db):
    out = await _run(_msg())
    assert out[0].text == NOT_BOUND_REPLY


@pytest.mark.asyncio
async def test_member_gets_reply_in_thread_and_own_history(db):
    _bind(db)
    out = await _run(_msg(text="gastei 10"), _agent("Confirma?"))

    assert out[0].text == "Confirma?"
    assert out[0].reply_to == "42"
    rows = db.tables["group_chat_history"]
    assert rows[0]["user_id"] == "ana" and rows[0]["chat_key"] == f"telegram:{CHAT}"
    assert "conversations" not in db.tables


@pytest.mark.asyncio
async def test_confirmation_of_one_member_does_not_leak_to_another(db):
    _bind(db)
    db.tables["group_members"].append({"id": "m2", "group_id": "g1", "user_id": "bia", "role": "member"})
    agent = _agent("ok")
    await _run(_msg(user="1", text="gastei 10"), agent)
    await _run(_msg(user="2", name="Bia", text="sim"), agent)

    prompt_bia = agent.arun.call_args_list[-1].args[0]
    assert "gastei 10" not in prompt_bia


@pytest.mark.asyncio
async def test_non_member_gets_approval_button(db):
    _bind(db)
    out = await _run(_msg(user="2", name="Bia"))

    assert "Bia ainda não participa do grupo financeiro Casa" in out[0].text
    assert out[0].buttons == (Button(label="Aprovar Bia", action="approve:bia"),)


@pytest.mark.asyncio
async def test_member_of_other_group_is_refused(db):
    _bind(db)
    db.tables["group_members"].append({"id": "m2", "group_id": "outro", "user_id": "bia", "role": "owner"})
    out = await _run(_msg(user="2", name="Bia"))
    assert "outro grupo financeiro" in out[0].text


def test_owner_approves_member(db):
    _bind(db)
    out = process_button(_msg(user="1", text="approve:bia"))
    assert "Bia agora faz parte do grupo Casa" in out[0].text
    assert {"group_id": "g1", "user_id": "bia", "role": "member"}.items() <= db.tables["group_members"][-1].items()


def test_only_owner_can_approve(db):
    _bind(db)
    db.tables["users"].append({"id": "caio", "name": "Caio"})
    out = process_button(_msg(user="2", name="Bia", text="approve:caio"))
    assert "Só o dono" in out[0].text
    assert len(db.tables["group_members"]) == 1


def test_approve_is_idempotent(db):
    _bind(db)
    process_button(_msg(user="1", text="approve:bia"))
    out = process_button(_msg(user="1", text="approve:bia"))
    assert "já participa" in out[0].text
    assert len(db.tables["group_members"]) == 2


def test_unknown_button_is_ignored(db):
    assert process_button(_msg(text="outra:coisa")) == []


def test_bind_and_unbind_commands(db):
    assert "vinculado ao grupo financeiro Casa" in bind_command(_msg(user="1", text=""))[0].text
    assert "já está vinculado" in bind_command(_msg(user="1", text=""))[0].text
    assert "Só o dono" in unbind_command(_msg(user="2", name="Bia", text=""))[0].text
    assert "desvinculado" in unbind_command(_msg(user="1", text=""))[0].text


def test_bind_requires_group_chat(db):
    out = bind_command(_msg(user="1", text="", chat_type="private"))
    assert "dentro do grupo do Telegram" in out[0].text


def test_bind_by_non_owner(db):
    assert "Só o dono de um grupo financeiro" in bind_command(_msg(user="2", name="Bia", text=""))[0].text


def test_chat_migration_moves_binding(db):
    _bind(db)
    chat_migrated("telegram", CHAT, "-100999")
    assert db.tables["chat_bindings"][0]["chat_id"] == "-100999"
