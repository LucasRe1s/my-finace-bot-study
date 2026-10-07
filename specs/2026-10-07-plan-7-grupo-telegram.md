# Fase 4: Bot em grupo do Telegram Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** O bot funciona dentro de um grupo do Telegram ligado a um grupo financeiro: membros registram e consultam pelo chat, quem ainda não é membro é aprovado pelo dono com um botão, e cada pessoa tem sua própria conversa com o bot.

**Architecture:** Nova tabela `chat_bindings` liga um chat a um grupo financeiro (no máximo um chat por grupo). O núcleo (`core/`) ganha a noção de chat de grupo: só processa mensagens dirigidas ao bot, confere se o remetente é do grupo ligado, guarda histórico por (usuário, chat) em `group_chat_history` e devolve respostas como "reply" à mensagem original, com botões opcionais. O adaptador Telegram traduz menção, resposta e `/f` em "dirigida ao bot", renderiza botões como inline keyboard e trata callback, entrada do bot no grupo e migração para supergrupo.

**Tech Stack:** Python 3.12, FastAPI, python-telegram-bot 22, supabase-py 2, pytest.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 4").

## Global Constraints

- Comandos a partir de `backend/`; testes com `.venv/bin/pytest -q`.
- Comentários e mensagens em português; sem travessão (—) em texto novo.
- Acesso sem usuário logado só via `get_service_supabase()`.
- `callback_data` do Telegram: até 64 bytes. `approve:` + UUID = 44.
- Commits com `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisões desta fase

- **Um chat por grupo financeiro** (`UNIQUE(group_id)` em `chat_bindings`), como proposto na spec.
- **Privacy mode:** a documentação do Telegram garante, com privacy mode ligado, a entrega de comandos e de respostas a mensagens do bot, mas **não** cita menções. Por isso há três formas de falar com o bot no grupo: responder a uma mensagem dele, `/f <texto>` e `@bot <texto>`. O núcleo só manda ao LLM o que foi dirigido ao bot (`addressed`), então desligar o privacy mode também é seguro.
- **Aprovação sem tabela de pedidos:** o botão carrega `approve:<user_id>`. Ao clicar, o backend confere que quem clicou é o dono do grupo ligado àquele chat e que a pessoa ainda não está em grupo nenhum. Um `callback_data` forjado não passa dessas checagens.
- **Histórico de grupo em tabela nova** (`group_chat_history`), em vez de mudar a `UNIQUE(user_id)` de `conversations`. Mudar a constraint quebraria o código antigo no meio do deploy (o `upsert ... on_conflict=user_id` deixaria de ter constraint correspondente); a tabela nova é aditiva.
- **Migração para supergrupo:** quando o Telegram converte um grupo em supergrupo, o `chat_id` muda e chega uma mensagem de serviço com `migrate_to_chat_id`. O vínculo é movido para o novo id.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/supabase/migrations/014_chat_bindings.sql` (novo) | `chat_bindings`, `group_chat_history` |
| `backend/app/services/chat_bindings.py` (novo) | Vincular, desvincular, achar e mover vínculo |
| `backend/app/services/membership.py` | `get_group` |
| `backend/agent/history.py` | Histórico por chat (`chat_key`) |
| `backend/core/messages.py` | `chat_type`, `addressed`, `message_id`; `reply_to`, `buttons`, `Button` |
| `backend/core/group_chat.py` (novo) | Acesso ao chat de grupo, aprovação, `/vincular`, `/desvincular`, boas-vindas, migração |
| `backend/core/conversation.py` | `process_message` ciente de grupo; `HELP_TEXT` |
| `backend/tgbot/handlers.py`, `runner.py`, `webhook.py` | Detecção de grupo, botões, callbacks, eventos de serviço |
| `backend/tests/fakes.py` | `upsert` com `on_conflict` de várias colunas |

---

### Task 1: Migration 014, serviço de vínculo e histórico por chat

**Files:**
- Create: `backend/supabase/migrations/014_chat_bindings.sql`, `backend/app/services/chat_bindings.py`
- Modify: `backend/app/services/membership.py`, `backend/agent/history.py`, `backend/tests/fakes.py`
- Test: `backend/tests/test_chat_bindings.py` (novo), `backend/tests/test_migrations.py`, `backend/tests/test_agent_history.py`

**Interfaces:**
- Produces:
  - `chat_bindings.find_binding(db, channel: str, chat_id: str) -> dict | None`
  - `chat_bindings.bind_chat(db, channel, chat_id, user_id) -> dict` (devolve o grupo; levanta `NotGroupOwner`, `ChatAlreadyBound`, `GroupAlreadyBound`)
  - `chat_bindings.unbind_chat(db, channel, chat_id, user_id) -> None` (levanta `ChatNotBound`, `NotGroupOwner`)
  - `chat_bindings.move_chat(db, channel, old_chat_id, new_chat_id) -> None`
  - `membership.get_group(db, group_id) -> dict | None`
  - `history.get_history(db, user_id, chat_key: str | None = None)` e `save_history(db, user_id, messages, chat_key: str | None = None)`

- [ ] **Step 1: Testes que falham**

`tests/test_migrations.py`, acrescentar:

```python
def test_chat_bindings_and_group_history():
    sql = _sql("014_chat_bindings.sql")
    assert "CREATE TABLE public.chat_bindings" in sql
    assert "UNIQUE (channel, chat_id)" in sql
    assert "UNIQUE (group_id)" in sql
    assert "CREATE TABLE public.group_chat_history" in sql
    assert "UNIQUE (user_id, chat_key)" in sql
    for table in ("chat_bindings", "group_chat_history"):
        assert f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;" in sql
        assert f"REVOKE ALL ON public.{table} FROM anon;" in sql
    assert not re.search(r"\bTO\s+anon\b", sql)
```

`tests/test_agent_history.py`, acrescentar:

```python
def test_group_history_is_separate_per_chat():
    from tests.fakes import FakeSupabase

    db = FakeSupabase()
    save_history(db, "u1", [{"role": "user", "content": "privado"}])
    save_history(db, "u1", [{"role": "user", "content": "grupo A"}], chat_key="telegram:-1")
    save_history(db, "u1", [{"role": "user", "content": "grupo A de novo"}], chat_key="telegram:-1")
    save_history(db, "u1", [{"role": "user", "content": "grupo B"}], chat_key="telegram:-2")

    assert get_history(db, "u1")[0]["content"] == "privado"
    assert get_history(db, "u1", "telegram:-1")[0]["content"] == "grupo A de novo"
    assert get_history(db, "u1", "telegram:-2")[0]["content"] == "grupo B"
    assert len(db.tables["group_chat_history"]) == 2
```

`tests/test_chat_bindings.py`:

```python
import pytest

from app.services.chat_bindings import (
    ChatAlreadyBound,
    ChatNotBound,
    GroupAlreadyBound,
    NotGroupOwner,
    bind_chat,
    find_binding,
    move_chat,
    unbind_chat,
)
from tests.fakes import FakeSupabase


@pytest.fixture
def db():
    fake = FakeSupabase(unique={"chat_bindings": [("channel", "chat_id"), ("group_id",)]})
    fake.tables["groups"] = [{"id": "g1", "name": "Casa", "owner_id": "ana"}]
    return fake


def test_owner_binds_chat(db):
    group = bind_chat(db, "telegram", "-100", "ana")
    assert group["id"] == "g1"
    assert find_binding(db, "telegram", "-100")["group_id"] == "g1"


def test_non_owner_cannot_bind(db):
    with pytest.raises(NotGroupOwner):
        bind_chat(db, "telegram", "-100", "bia")


def test_chat_cannot_be_bound_twice(db):
    db.tables["groups"].append({"id": "g2", "name": "Outro", "owner_id": "caio"})
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(ChatAlreadyBound):
        bind_chat(db, "telegram", "-100", "caio")


def test_group_has_at_most_one_chat(db):
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(GroupAlreadyBound):
        bind_chat(db, "telegram", "-200", "ana")


def test_unbind_by_owner(db):
    bind_chat(db, "telegram", "-100", "ana")
    unbind_chat(db, "telegram", "-100", "ana")
    assert find_binding(db, "telegram", "-100") is None


def test_unbind_rules(db):
    with pytest.raises(ChatNotBound):
        unbind_chat(db, "telegram", "-100", "ana")
    bind_chat(db, "telegram", "-100", "ana")
    with pytest.raises(NotGroupOwner):
        unbind_chat(db, "telegram", "-100", "bia")


def test_move_chat_after_supergroup_migration(db):
    bind_chat(db, "telegram", "-100", "ana")
    move_chat(db, "telegram", "-100", "-100999")
    assert find_binding(db, "telegram", "-100") is None
    assert find_binding(db, "telegram", "-100999")["group_id"] == "g1"
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/supabase/migrations/014_chat_bindings.sql`:

```sql
-- Fase 4: bot dentro de um grupo do Telegram.
--
-- chat_bindings: liga um chat (grupo do Telegram, e no futuro do WhatsApp) a
-- um grupo financeiro. No maximo um chat por grupo financeiro.
-- group_chat_history: historico do bot por (usuario, chat de grupo), para a
-- confirmacao pendente de uma pessoa nao ser confirmada por outra. O historico
-- do privado continua em conversations (mudar a UNIQUE(user_id) de la
-- quebraria o codigo antigo durante o deploy).
--
-- Escrita e leitura so pelo backend (service_role). Aditiva: pode ser
-- aplicada antes do deploy.

CREATE TABLE public.chat_bindings (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp')),
  chat_id TEXT NOT NULL,
  group_id UUID REFERENCES public.groups(id) ON DELETE CASCADE NOT NULL,
  created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (channel, chat_id),
  UNIQUE (group_id)
);

CREATE TABLE public.group_chat_history (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  chat_key TEXT NOT NULL,
  messages JSONB NOT NULL DEFAULT '[]',
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, chat_key)
);

ALTER TABLE public.chat_bindings ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_chat_history ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON public.chat_bindings FROM anon;
REVOKE ALL ON public.group_chat_history FROM anon;
```

`backend/tests/fakes.py`, ramo `upsert` de `execute`, para aceitar `on_conflict="a,b"`:

```python
        if self._op == "upsert":
            keys = [k.strip() for k in self._on_conflict.split(",")]
            existing = next(
                (row for row in rows if all(row.get(k) == self._payload.get(k) for k in keys)), None
            )
```

(o restante do ramo continua igual).

`backend/app/services/membership.py`, acrescentar:

```python
def get_group(db: Client, group_id: str) -> dict | None:
    result = db.table("groups").select("*").eq("id", group_id).maybe_single().execute()
    return result.data if result else None
```

`backend/app/services/chat_bindings.py`:

```python
"""Vinculo entre um chat de grupo (Telegram, futuramente WhatsApp) e um grupo
financeiro. `db` e o client de servico."""
from supabase import Client


class NotGroupOwner(Exception):
    """Quem pediu nao e dono do grupo financeiro."""


class ChatAlreadyBound(Exception):
    """O chat ja esta ligado a um grupo financeiro."""


class GroupAlreadyBound(Exception):
    """O grupo financeiro ja esta ligado a outro chat."""


class ChatNotBound(Exception):
    """O chat nao esta ligado a nenhum grupo financeiro."""


def find_binding(db: Client, channel: str, chat_id: str) -> dict | None:
    result = (
        db.table("chat_bindings")
        .select("*")
        .eq("channel", channel)
        .eq("chat_id", chat_id)
        .maybe_single()
        .execute()
    )
    return result.data if result else None


def _owned_group(db: Client, user_id: str) -> dict | None:
    result = db.table("groups").select("*").eq("owner_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def bind_chat(db: Client, channel: str, chat_id: str, user_id: str) -> dict:
    group = _owned_group(db, user_id)
    if group is None:
        raise NotGroupOwner()
    if find_binding(db, channel, chat_id) is not None:
        raise ChatAlreadyBound()
    if db.table("chat_bindings").select("id").eq("group_id", group["id"]).limit(1).execute().data:
        raise GroupAlreadyBound()
    db.table("chat_bindings").insert(
        {"channel": channel, "chat_id": chat_id, "group_id": group["id"], "created_by": user_id}
    ).execute()
    return group


def unbind_chat(db: Client, channel: str, chat_id: str, user_id: str) -> None:
    binding = find_binding(db, channel, chat_id)
    if binding is None:
        raise ChatNotBound()
    owned = _owned_group(db, user_id)
    if owned is None or owned["id"] != binding["group_id"]:
        raise NotGroupOwner()
    db.table("chat_bindings").delete().eq("id", binding["id"]).execute()


def move_chat(db: Client, channel: str, old_chat_id: str, new_chat_id: str) -> None:
    db.table("chat_bindings").update({"chat_id": new_chat_id}).eq("channel", channel).eq("chat_id", old_chat_id).execute()
```

`backend/agent/history.py` (substitui o arquivo):

```python
from datetime import datetime, timezone

from supabase import Client

MAX_HISTORY = 10


def _table(chat_key: str | None) -> str:
    # Privado em conversations; cada chat de grupo em group_chat_history.
    return "group_chat_history" if chat_key else "conversations"


def get_history(db: Client, user_id: str, chat_key: str | None = None) -> list[dict]:
    query = db.table(_table(chat_key)).select("messages").eq("user_id", user_id)
    if chat_key:
        query = query.eq("chat_key", chat_key)
    result = query.maybe_single().execute()
    if not result or not result.data:
        return []
    return result.data.get("messages", [])


def save_history(db: Client, user_id: str, messages: list[dict], chat_key: str | None = None) -> None:
    row = {
        "user_id": user_id,
        "messages": messages[-MAX_HISTORY:],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if chat_key:
        row["chat_key"] = chat_key
    db.table(_table(chat_key)).upsert(
        row, on_conflict="user_id,chat_key" if chat_key else "user_id"
    ).execute()
```

- [ ] **Step 4: Rodar a suíte.** Os testes antigos de `test_agent_history.py` usam mocks de `upsert`; conferir que continuam verdes.
- [ ] **Step 5: Commit** `feat(db): vinculo de chat de grupo e historico por chat`

---

### Task 2: Núcleo ciente de chat de grupo

**Files:**
- Modify: `backend/core/messages.py`, `backend/core/conversation.py`
- Create: `backend/core/group_chat.py`
- Test: `backend/tests/test_group_chat.py` (novo)

**Interfaces:**
- Consumes: Task 1.
- Produces:
  - `IncomingMessage` ganha `chat_type: str = "private"`, `addressed: bool = True`, `message_id: str | None = None`.
  - `Button(label: str, action: str)`; `OutgoingMessage` ganha `reply_to: str | None = None` e `buttons: tuple[Button, ...] = ()`.
  - `core.group_chat`: `chat_key(msg) -> str`, `group_access_refusal(db, msg, user) -> list[OutgoingMessage] | None`, `process_button(msg) -> list[OutgoingMessage]`, `bind_command(msg)`, `unbind_command(msg)`, `group_welcome(msg)`, `chat_migrated(channel, old_chat_id, new_chat_id) -> None`, constantes `NOT_BOUND_REPLY`, `APPROVE_PREFIX = "approve:"`.
  - `process_message` devolve `[]` para mensagem de grupo não dirigida ao bot e responde em reply (`reply_to=msg.message_id`) nos grupos.

- [ ] **Step 1: Testes que falham**

`backend/tests/test_group_chat.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/core/messages.py` (substitui o arquivo):

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class IncomingMessage:
    """Mensagem de texto recebida por qualquer canal, ja normalizada."""
    channel: str
    external_user_id: str
    display_name: str
    chat_id: str
    text: str
    chat_type: str = "private"  # "private" ou "group"
    # Em grupo: a mensagem foi dirigida ao bot (resposta, comando ou mencao).
    addressed: bool = True
    message_id: str | None = None


@dataclass(frozen=True)
class Button:
    label: str
    # Enviado de volta ao nucleo quando clicado (Telegram: callback_data, ate 64 bytes).
    action: str


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
    reply_to: str | None = None
    buttons: tuple[Button, ...] = ()
```

`backend/core/group_chat.py`:

```python
"""Regras do bot dentro de um chat de grupo ligado a um grupo financeiro."""
import logging

from app.database import get_service_supabase
from app.services.chat_bindings import (
    ChatAlreadyBound,
    ChatNotBound,
    GroupAlreadyBound,
    NotGroupOwner,
    bind_chat,
    find_binding,
    move_chat,
    unbind_chat,
)
from app.services.identities import get_or_create_user
from app.services.membership import find_user_group, get_group, names_by_id

from .messages import Button, IncomingMessage, OutgoingMessage

logger = logging.getLogger("bot")

APPROVE_PREFIX = "approve:"
NOT_BOUND_REPLY = (
    "Este chat ainda não está ligado a um grupo financeiro. "
    "O dono do grupo financeiro precisa enviar /vincular aqui."
)
GROUP_WELCOME = (
    "Olá! Sou o Assistente Financeiro.\n\n"
    "Para começar, o dono do grupo financeiro envia /vincular aqui.\n"
    "Depois, para falar comigo neste chat, responda a uma mensagem minha "
    "ou use /f, por exemplo: /f gastei R$ 50 no mercado."
)


def chat_key(msg: IncomingMessage) -> str:
    return f"{msg.channel}:{msg.chat_id}"


def _reply(msg: IncomingMessage, text: str, buttons: tuple[Button, ...] = ()) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=text, reply_to=msg.message_id, buttons=buttons)]


def group_access_refusal(db, msg: IncomingMessage, user: dict) -> list[OutgoingMessage] | None:
    """None se o remetente pode usar o bot neste chat; senao, a resposta."""
    binding = find_binding(db, msg.channel, msg.chat_id)
    if binding is None:
        return _reply(msg, NOT_BOUND_REPLY)

    user_group = find_user_group(db, user["id"])
    if user_group == binding["group_id"]:
        return None
    if user_group is not None:
        return _reply(msg, "Você participa de outro grupo financeiro, então não posso registrar seus lançamentos aqui.")

    group = get_group(db, binding["group_id"]) or {}
    name = user.get("name") or msg.display_name or "Esta pessoa"
    return _reply(
        msg,
        f"{name} ainda não participa do grupo financeiro {group.get('name', '')}. "
        "O dono do grupo pode aprovar pelo botão abaixo.",
        buttons=(Button(label=f"Aprovar {name}", action=f"{APPROVE_PREFIX}{user['id']}"),),
    )


def process_button(msg: IncomingMessage) -> list[OutgoingMessage]:
    if not msg.text.startswith(APPROVE_PREFIX):
        return []
    target_id = msg.text[len(APPROVE_PREFIX):]
    db = get_service_supabase()
    try:
        approver, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        binding = find_binding(db, msg.channel, msg.chat_id)
        if binding is None:
            return _reply(msg, NOT_BOUND_REPLY)
        group = get_group(db, binding["group_id"])
        if group is None or group["owner_id"] != approver["id"]:
            return _reply(msg, "Só o dono do grupo financeiro pode aprovar novos membros.")
        name = names_by_id(db, [target_id]).get(target_id) or "Novo membro"
        if find_user_group(db, target_id) is not None:
            return _reply(msg, f"{name} já participa de um grupo financeiro.")
        db.table("group_members").insert({"group_id": group["id"], "user_id": target_id, "role": "member"}).execute()
    except Exception:
        logger.exception("Falha ao aprovar membro no chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível aprovar agora. Tente novamente em instantes.")
    return _reply(msg, f"{name} agora faz parte do grupo {group['name']}.")


def bind_command(msg: IncomingMessage) -> list[OutgoingMessage]:
    if msg.chat_type != "group":
        return _reply(msg, "Use /vincular dentro do grupo do Telegram que você quer ligar ao grupo financeiro.")
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group = bind_chat(db, msg.channel, msg.chat_id, user["id"])
    except NotGroupOwner:
        return _reply(msg, (
            "Só o dono de um grupo financeiro pode vincular este chat. "
            "Crie o grupo financeiro falando comigo no privado e depois envie /vincular aqui."
        ))
    except ChatAlreadyBound:
        return _reply(msg, "Este chat já está vinculado a um grupo financeiro.")
    except GroupAlreadyBound:
        return _reply(msg, "Seu grupo financeiro já está vinculado a outro chat. Envie /desvincular lá primeiro.")
    except Exception:
        logger.exception("Falha ao vincular chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível vincular agora. Tente novamente em instantes.")
    return _reply(msg, (
        f"Chat vinculado ao grupo financeiro {group['name']}.\n\n"
        "Para falar comigo aqui, responda a uma mensagem minha ou use /f, "
        "por exemplo: /f gastei R$ 50 no mercado. "
        "Quem ainda não participa do grupo financeiro será aprovado por você."
    ))


def unbind_command(msg: IncomingMessage) -> list[OutgoingMessage]:
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        unbind_chat(db, msg.channel, msg.chat_id, user["id"])
    except ChatNotBound:
        return _reply(msg, "Este chat não está vinculado a nenhum grupo financeiro.")
    except NotGroupOwner:
        return _reply(msg, "Só o dono do grupo financeiro pode desvincular este chat.")
    except Exception:
        logger.exception("Falha ao desvincular chat %s", msg.chat_id)
        return _reply(msg, "Não foi possível desvincular agora. Tente novamente em instantes.")
    return _reply(msg, "Chat desvinculado. Os dados do grupo financeiro continuam salvos.")


def group_welcome(msg: IncomingMessage) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=GROUP_WELCOME)]


def chat_migrated(channel: str, old_chat_id: str, new_chat_id: str) -> None:
    move_chat(get_service_supabase(), channel, old_chat_id, new_chat_id)
```

`backend/core/conversation.py`:

1. Imports: `from .group_chat import chat_key, group_access_refusal`.
2. `_reply` passa a responder em thread nos grupos:

```python
def _reply(msg: IncomingMessage, text: str) -> list[OutgoingMessage]:
    reply_to = msg.message_id if msg.chat_type == "group" else None
    return [OutgoingMessage(chat_id=msg.chat_id, text=text, reply_to=reply_to)]
```

3. Em `process_message`, antes do rate limit:

```python
    if msg.chat_type == "group" and not msg.addressed:
        return []
```

4. Dentro do `try`, logo após `get_or_create_user`, e trocando as chamadas de histórico:

```python
        history_key = None
        if msg.chat_type == "group":
            refusal = group_access_refusal(db, msg, user)
            if refusal:
                return refusal
            history_key = chat_key(msg)
        history = get_history(db, user["id"], history_key)
```

e `save_history(db, user["id"], history, history_key)`.

5. `HELP_TEXT` ganha, depois da linha de `/convidar`:

```python
    "/vincular: ligar um grupo do Telegram ao seu grupo financeiro (no grupo)\n"
    "/desvincular: desligar o grupo do Telegram (no grupo)\n"
    "/f <mensagem>: falar comigo dentro de um grupo do Telegram\n"
```

- [ ] **Step 4: Rodar a suíte** (os testes de `test_conversation.py` usam mensagens privadas e não mudam).
- [ ] **Step 5: Commit** `feat(core): bot em chat de grupo com aprovacao do dono e historico por pessoa`

---

### Task 3: Adaptador Telegram para grupos

**Files:**
- Modify: `backend/tgbot/handlers.py`, `backend/tgbot/runner.py`, `backend/tgbot/webhook.py`
- Test: `backend/tests/test_telegram_handlers.py`, `backend/tests/test_telegram_webhook.py`

**Interfaces:**
- Consumes: Task 2.
- Produces: handlers `handle_bind`, `handle_unbind`, `handle_f`, `handle_button`, `handle_new_members`, `handle_migration`; `ALLOWED_UPDATES = ["message", "callback_query"]` em `tgbot/runner.py`, usado no polling e no `set_webhook`.

- [ ] **Step 1: Testes que falham**

Em `tests/test_telegram_handlers.py`:

1. O helper `_update` passa a fixar o tipo de chat e o reply:

```python
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
```

2. O helper `_context` fixa a identidade do bot:

```python
    context.bot.id = 999
    context.bot.username = "finncyBot"
```

3. Novos testes:

```python
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
```

Em `test_message_is_converted_and_replies_are_sent`, o `IncomingMessage` esperado ganha `message_id="7"`.

Em `tests/test_telegram_webhook.py`, no teste do lifespan, a asserção de `set_webhook` passa a usar `allowed_updates=["message", "callback_query"]`.

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/tgbot/handlers.py` (substitui o arquivo):

```python
# -*- coding: utf-8 -*-
"""Adaptador Telegram: converte Update em IncomingMessage, chama o nucleo e
envia as respostas. Sem regra de negocio aqui."""
import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyParameters, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.config import settings
from core.conversation import help_message, invite_command, process_message, process_start
from core.group_chat import bind_command, chat_migrated, group_welcome, process_button, unbind_command
from core.messages import IncomingMessage, OutgoingMessage

CHANNEL = "telegram"


def _is_group(update: Update) -> bool:
    return update.effective_chat.type != "private"


def _incoming(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str | None = None, addressed: bool | None = None) -> IncomingMessage:
    message = update.message
    raw = message.text if text is None else text
    raw = raw or ""
    group = _is_group(update)
    if group and addressed is None:
        mention = f"@{context.bot.username}"
        replied = message.reply_to_message is not None and message.reply_to_message.from_user.id == context.bot.id
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
```

Observação: a regra "só o que é dirigido ao bot" fica nos dois lugares de propósito. O núcleo devolve `[]` (vale para qualquer canal); o adaptador retorna antes para não mostrar "digitando..." numa conversa que não é com o bot.

`backend/tgbot/runner.py`:

1. `ALLOWED_UPDATES = ["message", "callback_query"]` no topo, usado em `run_polling(allowed_updates=ALLOWED_UPDATES)`.
2. Imports e handlers:

```python
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

from .handlers import (
    handle_bind,
    handle_button,
    handle_f,
    handle_help,
    handle_invite,
    handle_message,
    handle_migration,
    handle_new_members,
    handle_start,
    handle_unbind,
)
```

```python
    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ajuda", handle_help))
    app.add_handler(CommandHandler("convidar", handle_invite))
    app.add_handler(CommandHandler("vincular", handle_bind))
    app.add_handler(CommandHandler("desvincular", handle_unbind))
    app.add_handler(CommandHandler("f", handle_f))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_members))
    app.add_handler(MessageHandler(filters.StatusUpdate.MIGRATE, handle_migration))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
```

`backend/tgbot/webhook.py`: importar `ALLOWED_UPDATES` de `.runner` e usar `allowed_updates=ALLOWED_UPDATES` no `set_webhook`.

- [ ] **Step 4: Rodar a suíte e um smoke test de grupo** com o python-telegram-bot real contra a Bot API falsa: `/vincular` da dona, `@bot` de um não membro (resposta com botão), clique em "Aprovar" (`callback_query`), mensagem do novo membro respondida em thread, mensagem sem menção ignorada.
- [ ] **Step 5: Commit** `feat(bot): grupos do Telegram com /vincular, /f, mencao e aprovacao por botao`

---

### Task 4: Documentação

- [ ] README: seção "Usando em um grupo do Telegram": adicionar o bot ao grupo, `/vincular` pelo dono, as três formas de falar com o bot, aprovação, `/desvincular`. Explicar privacy mode (ligado por padrão; desligar no @BotFather com `/setprivacy` faz a menção `@bot` funcionar sempre, e o bot continua ignorando o que não é para ele). Deploy cita a migration 014 (aditiva).
- [ ] PENDENTE: Fase 4 em "Concluido".
- [ ] Spec: Fase 4 aponta para este plano e registra as decisões (1 chat por grupo, `/f`, aprovação sem tabela, histórico em tabela nova, migração para supergrupo).
- [ ] Commit `docs: fase 4 (bot em grupo do Telegram)`.
