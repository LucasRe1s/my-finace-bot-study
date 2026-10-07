# Fase 2: Núcleo agnóstico de canal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar a lógica de conversa do Telegram e trocar `users.telegram_id` por identidades por canal, para que o WhatsApp (Fase 5) seja só mais um adaptador.

**Architecture:** Nova tabela `user_identities (channel, external_id → user_id)`. Um pacote `core/` recebe `IncomingMessage` e devolve `list[OutgoingMessage]`, cuidando de identidade, rate limit, agente, blindagens, histórico e alertas de limite. `tgbot/handlers.py` vira um adaptador fino que converte `Update` e envia as mensagens.

**Tech Stack:** Python 3.12, FastAPI, python-telegram-bot 22, supabase-py 2, pytest.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 2").

## Global Constraints

- Comandos a partir de `backend/`; testes com `.venv/bin/pytest -q`.
- Comentários e mensagens ao usuário em português. Não usar travessão (—) em texto novo; textos movidos de lugar perdem o travessão.
- Acesso ao banco sem usuário logado só via `get_service_supabase()`.
- `pyproject.toml` precisa incluir o novo pacote `core*`, senão o `pip install .` do Render não o instala.
- Commits com `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Ajustes em relação à spec

- **Sem renomear `telegram_link_codes`.** O código é gerado na web e não pertence a canal nenhum; o canal só importa no consumo, que vira `link_identity(db, code, channel, external_id)`. Renomear a tabela só criaria migração sem ganho.
- **`Notifier` adiado.** Hoje a única mensagem "proativa" é o alerta de limite, que acontece dentro do processamento de uma mensagem. Ele passa a voltar como `OutgoingMessage`. Um `Notifier` só será necessário quando houver envio fora de uma conversa (Fase 4 ou 5).
- **`mentions_bot` e `chat_type` adiados para a Fase 4**, quando o modo grupo existir.
- **`users.telegram_id` continua existindo** nesta fase. Um fallback adota usuários antigos (cria a identidade na primeira mensagem). A coluna sai numa fase posterior, junto com o fallback.

## Bugs corrigidos no caminho (vínculo de conta)

1. `groups.owner_id` tem `ON DELETE CASCADE`. O merge antigo apagava o usuário só-bot sem transferir a posse do grupo, apagando o grupo e todas as transações dele. Agora a posse é transferida antes.
2. `conversations.user_id` é `UNIQUE`. Mover o histórico do usuário antigo para um alvo que já tem histórico violava a constraint no meio do merge. Agora o histórico antigo é descartado (é efêmero).
3. Se as duas contas já participam de grupos diferentes, o vínculo é recusado com `LinkConflict` em vez de deixar o usuário em dois grupos. O código não é consumido nesse caso.
4. O código passa a ser reivindicado com `UPDATE ... WHERE used_at IS NULL`, então não pode ser usado duas vezes em paralelo.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/supabase/migrations/012_user_identities.sql` (novo) | Tabela, RLS, backfill a partir de `users.telegram_id` |
| `backend/app/services/identities.py` (novo) | Achar/criar usuário por identidade, vincular código, merge |
| `backend/app/services/user_token.py` (novo) | JWT do usuário para o bot (sai de `tgbot/handlers.py`) |
| `backend/app/services/telegram_link.py` | Removido (substituído por `identities.py`) |
| `backend/core/__init__.py` (novo) | Pacote |
| `backend/core/messages.py` (novo) | `IncomingMessage`, `OutgoingMessage` |
| `backend/core/rate_limit.py` (novo) | `SlidingWindowLimiter` |
| `backend/core/alerts.py` (novo) | `limit_alert_message` (sai de `tgbot/alerts.py`) |
| `backend/core/conversation.py` (novo) | `process_message`, `process_start`, `help_message` |
| `backend/tgbot/alerts.py` | Removido |
| `backend/agent/tools.py` | `alert_sink` no lugar de `bot`/`telegram_id` |
| `backend/tgbot/handlers.py` | Adaptador fino |
| `backend/pyproject.toml` | Inclui `core*` |
| `backend/tests/fakes.py` (novo) | `FakeSupabase` em memória com constraints únicas |

---

### Task 1: Migration 012 e FakeSupabase

**Files:**
- Create: `backend/supabase/migrations/012_user_identities.sql`
- Create: `backend/tests/fakes.py`
- Modify: `backend/tests/test_migrations.py`
- Test: `backend/tests/test_fakes.py`

**Interfaces:**
- Produces: tabela `user_identities(id, user_id, channel, external_id, created_at)`; `tests.fakes.FakeSupabase(unique: dict[str, list[tuple[str, ...]]] | None = None)` com `.tables: dict[str, list[dict]]` e a API encadeada usada no código (`table/select/insert/update/upsert/delete/eq/is_/gte/limit/maybe_single/execute`). `maybe_single().execute()` devolve `None` sem linhas, como o supabase-py.

- [ ] **Step 1: Testes que falham**

Em `tests/test_migrations.py`, acrescentar:

```python
def test_user_identities_has_rls_and_no_anon():
    sql = _sql("012_user_identities.sql")
    assert "CREATE TABLE public.user_identities" in sql
    assert "UNIQUE (channel, external_id)" in sql
    assert "ALTER TABLE public.user_identities ENABLE ROW LEVEL SECURITY;" in sql
    assert "REVOKE ALL ON public.user_identities FROM anon;" in sql
    assert not re.search(r"\bTO\s+anon\b", sql)


def test_user_identities_backfills_telegram_ids():
    sql = _sql("012_user_identities.sql")
    assert re.search(r"INSERT INTO public\.user_identities.*FROM public\.users.*telegram_id IS NOT NULL", sql, re.S)
```

`tests/test_fakes.py`:

```python
import pytest

from tests.fakes import FakeSupabase, UniqueViolation


def test_insert_select_update_delete():
    db = FakeSupabase()
    created = db.table("users").insert({"name": "Ana"}).execute().data[0]
    assert db.table("users").select("*").eq("id", created["id"]).maybe_single().execute().data["name"] == "Ana"

    db.table("users").update({"name": "Ana Maria"}).eq("id", created["id"]).execute()
    assert db.tables["users"][0]["name"] == "Ana Maria"

    db.table("users").delete().eq("id", created["id"]).execute()
    assert db.table("users").select("*").eq("id", created["id"]).maybe_single().execute() is None


def test_unique_constraint():
    db = FakeSupabase(unique={"user_identities": [("channel", "external_id")]})
    db.table("user_identities").insert({"channel": "telegram", "external_id": "1", "user_id": "a"}).execute()
    with pytest.raises(UniqueViolation):
        db.table("user_identities").insert({"channel": "telegram", "external_id": "1", "user_id": "b"}).execute()


def test_is_null_and_gte_filters():
    db = FakeSupabase()
    db.tables["codes"] = [
        {"code": "A", "used_at": None, "expires_at": "2030-01-01"},
        {"code": "B", "used_at": "x", "expires_at": "2030-01-01"},
        {"code": "C", "used_at": None, "expires_at": "2020-01-01"},
    ]
    rows = db.table("codes").select("*").is_("used_at", "null").gte("expires_at", "2026-01-01").execute().data
    assert [r["code"] for r in rows] == ["A"]
```

- [ ] **Step 2: Rodar e ver falhar** (`FileNotFoundError` e `ModuleNotFoundError: tests.fakes`).

- [ ] **Step 3: Implementação**

`backend/supabase/migrations/012_user_identities.sql`:

```sql
-- Fase 2: identidades por canal (Telegram hoje, WhatsApp na Fase 5).
--
-- Substitui public.users.telegram_id. A coluna continua existindo nesta fase:
-- o backend adota usuarios antigos na primeira mensagem
-- (app/services/identities.py::_adopt_legacy_telegram_user) e ela sai numa
-- migration futura.
--
-- Pode ser aplicada antes do deploy do codigo novo: so adiciona.

CREATE TABLE public.user_identities (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  user_id UUID REFERENCES public.users(id) ON DELETE CASCADE NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('telegram', 'whatsapp')),
  external_id TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (channel, external_id)
);

CREATE INDEX user_identities_user_id_idx ON public.user_identities (user_id);

ALTER TABLE public.user_identities ENABLE ROW LEVEL SECURITY;

-- Usuario logado ve as proprias identidades (ex.: painel mostrar "Telegram vinculado").
-- Escrita so pelo backend, via service_role.
CREATE POLICY "user_identities_own_select" ON public.user_identities
  FOR SELECT TO authenticated USING (auth.uid() = user_id);

GRANT SELECT ON public.user_identities TO authenticated;
REVOKE ALL ON public.user_identities FROM anon;

INSERT INTO public.user_identities (user_id, channel, external_id)
SELECT id, 'telegram', telegram_id::text
FROM public.users
WHERE telegram_id IS NOT NULL
ON CONFLICT (channel, external_id) DO NOTHING;
```

`backend/tests/fakes.py`:

```python
"""Supabase em memoria para testes de servicos com varias queries encadeadas,
onde mocks de cadeia (table().select().eq()...) ficam ilegiveis. Cobre so o
subconjunto da API usado no projeto."""
from uuid import uuid4


class UniqueViolation(Exception):
    pass


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, db: "FakeSupabase", table: str):
        self._db = db
        self._table = table
        self._filters = []
        self._op = "select"
        self._payload = None
        self._on_conflict = None
        self._single = False
        self._limit = None

    def select(self, *_args):
        self._op = "select"
        return self

    def insert(self, payload):
        self._op, self._payload = "insert", payload
        return self

    def update(self, payload):
        self._op, self._payload = "update", payload
        return self

    def upsert(self, payload, on_conflict="id"):
        self._op, self._payload, self._on_conflict = "upsert", payload, on_conflict
        return self

    def delete(self):
        self._op = "delete"
        return self

    def eq(self, column, value):
        self._filters.append(lambda row: row.get(column) == value)
        return self

    def is_(self, column, value):
        assert value == "null", "FakeSupabase so suporta is_(col, 'null')"
        self._filters.append(lambda row: row.get(column) is None)
        return self

    def gte(self, column, value):
        self._filters.append(lambda row: row.get(column) is not None and row[column] >= value)
        return self

    def limit(self, n):
        self._limit = n
        return self

    def maybe_single(self):
        self._single = True
        return self

    def execute(self):
        rows = self._db.tables.setdefault(self._table, [])
        matched = [row for row in rows if all(f(row) for f in self._filters)]

        if self._op == "select":
            data = [dict(row) for row in matched][: self._limit]
            if self._single:
                return _Result(data[0]) if data else None
            return _Result(data)

        if self._op == "insert":
            items = self._payload if isinstance(self._payload, list) else [self._payload]
            created = []
            for item in items:
                row = {"id": str(uuid4()), **item}
                self._db.check_unique(self._table, row)
                rows.append(row)
                created.append(dict(row))
            return _Result(created)

        if self._op == "update":
            for row in matched:
                self._db.check_unique(self._table, {**row, **self._payload}, ignore=row)
                row.update(self._payload)
            return _Result([dict(row) for row in matched])

        if self._op == "upsert":
            key = self._on_conflict
            existing = next((row for row in rows if row.get(key) == self._payload.get(key)), None)
            if existing:
                existing.update(self._payload)
                return _Result([dict(existing)])
            row = {"id": str(uuid4()), **self._payload}
            rows.append(row)
            return _Result([dict(row)])

        if self._op == "delete":
            for row in matched:
                rows.remove(row)
            return _Result([dict(row) for row in matched])

        raise AssertionError(f"operacao desconhecida: {self._op}")


class FakeSupabase:
    def __init__(self, unique: dict[str, list[tuple[str, ...]]] | None = None):
        self.tables: dict[str, list[dict]] = {}
        self._unique = unique or {}

    def table(self, name: str) -> _Query:
        return _Query(self, name)

    def check_unique(self, table: str, candidate: dict, ignore: dict | None = None) -> None:
        for columns in self._unique.get(table, []):
            key = tuple(candidate.get(c) for c in columns)
            for row in self.tables.get(table, []):
                if row is not ignore and tuple(row.get(c) for c in columns) == key:
                    raise UniqueViolation(f"{table}{columns}={key}")
```

- [ ] **Step 4: Rodar a suíte** (tudo verde).
- [ ] **Step 5: Commit** `feat(db): tabela user_identities e FakeSupabase para testes`

---

### Task 2: Serviço de identidades (substitui `telegram_link.py`)

**Files:**
- Create: `backend/app/services/identities.py`
- Create: `backend/app/services/user_token.py`
- Delete: `backend/app/services/telegram_link.py`, `backend/tests/test_telegram_link_service.py`
- Test: `backend/tests/test_identities.py`

**Interfaces:**
- Consumes: `FakeSupabase` (Task 1).
- Produces:
  - `get_or_create_user(db, channel: str, external_id: str, display_name: str) -> tuple[dict, bool]`
  - `find_user_by_identity(db, channel: str, external_id: str) -> dict | None`
  - `link_identity(db, code: str, channel: str, external_id: str) -> None`, levantando `InvalidLinkCode` ou `LinkConflict`
  - `app.services.user_token.generate_user_token(user_id: str) -> str`

- [ ] **Step 1: Testes que falham**

`backend/tests/test_identities.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.services.identities import (
    InvalidLinkCode,
    LinkConflict,
    find_user_by_identity,
    get_or_create_user,
    link_identity,
)
from tests.fakes import FakeSupabase

FUTURE = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()


@pytest.fixture
def db():
    return FakeSupabase(unique={
        "user_identities": [("channel", "external_id")],
        "conversations": [("user_id",)],
    })


def _identity(db, user_id, external_id="555", channel="telegram"):
    db.tables.setdefault("user_identities", []).append(
        {"id": f"ident-{user_id}", "user_id": user_id, "channel": channel, "external_id": external_id}
    )


def _code(db, user_id="web-user", code="ABC12345", expires_at=FUTURE):
    db.tables.setdefault("telegram_link_codes", []).append(
        {"code": code, "user_id": user_id, "expires_at": expires_at, "used_at": None}
    )


def test_creates_user_and_identity_on_first_contact(db):
    user, is_new = get_or_create_user(db, "telegram", "555", "Ana")

    assert is_new
    assert user["name"] == "Ana"
    assert db.tables["user_identities"][0] == {
        "id": db.tables["user_identities"][0]["id"],
        "user_id": user["id"], "channel": "telegram", "external_id": "555",
    }


def test_finds_existing_user_by_identity(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana"}]
    _identity(db, "u1")

    user, is_new = get_or_create_user(db, "telegram", "555", "Outro nome")

    assert not is_new
    assert user["id"] == "u1"
    assert len(db.tables["users"]) == 1


def test_same_external_id_on_other_channel_is_another_user(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana"}]
    _identity(db, "u1", channel="telegram")

    user, is_new = get_or_create_user(db, "whatsapp", "555", "Ana")

    assert is_new
    assert user["id"] != "u1"


def test_adopts_legacy_telegram_user_without_identity(db):
    db.tables["users"] = [{"id": "legacy", "name": "Ana", "telegram_id": 555}]

    user = find_user_by_identity(db, "telegram", "555")

    assert user["id"] == "legacy"
    assert db.tables["user_identities"][0]["user_id"] == "legacy"


def test_link_adds_identity_to_web_account(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert find_user_by_identity(db, "telegram", "555")["id"] == "web-user"
    assert db.tables["telegram_link_codes"][0]["used_at"] is not None


def test_link_rejects_expired_code(db):
    _code(db, expires_at=PAST)
    with pytest.raises(InvalidLinkCode):
        link_identity(db, "ABC12345", "telegram", "555")


def test_link_code_works_only_once(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}]
    _code(db)
    link_identity(db, "ABC12345", "telegram", "555")
    with pytest.raises(InvalidLinkCode):
        link_identity(db, "ABC12345", "telegram", "777")


def test_link_merges_bot_only_user_keeping_its_group(db):
    db.tables["users"] = [{"id": "web-user", "name": "ana@x.com"}, {"id": "bot-user", "name": "Ana"}]
    _identity(db, "bot-user")
    db.tables["groups"] = [{"id": "g1", "name": "Casa", "owner_id": "bot-user"}]
    db.tables["group_members"] = [{"id": "m1", "group_id": "g1", "user_id": "bot-user", "role": "owner"}]
    db.tables["transactions"] = [{"id": "t1", "group_id": "g1", "user_id": "bot-user"}]
    db.tables["conversations"] = [
        {"id": "c1", "user_id": "bot-user", "messages": []},
        {"id": "c2", "user_id": "web-user", "messages": []},
    ]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["groups"][0]["owner_id"] == "web-user"
    assert db.tables["group_members"] == [{"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"}]
    assert db.tables["transactions"][0]["user_id"] == "web-user"
    assert [c["user_id"] for c in db.tables["conversations"]] == ["web-user"]
    assert [u["id"] for u in db.tables["users"]] == ["web-user"]
    assert find_user_by_identity(db, "telegram", "555")["id"] == "web-user"


def test_link_refuses_when_both_accounts_have_different_groups(db):
    db.tables["users"] = [{"id": "web-user"}, {"id": "bot-user"}]
    _identity(db, "bot-user")
    db.tables["group_members"] = [
        {"id": "m1", "group_id": "g-bot", "user_id": "bot-user", "role": "owner"},
        {"id": "m2", "group_id": "g-web", "user_id": "web-user", "role": "owner"},
    ]
    _code(db)

    with pytest.raises(LinkConflict):
        link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["telegram_link_codes"][0]["used_at"] is None
    assert {u["id"] for u in db.tables["users"]} == {"web-user", "bot-user"}


def test_link_when_both_in_same_group_drops_duplicate_membership(db):
    db.tables["users"] = [{"id": "web-user"}, {"id": "bot-user"}]
    _identity(db, "bot-user")
    db.tables["groups"] = [{"id": "g1", "owner_id": "web-user"}]
    db.tables["group_members"] = [
        {"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"},
        {"id": "m2", "group_id": "g1", "user_id": "bot-user", "role": "member"},
    ]
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert db.tables["group_members"] == [{"id": "m1", "group_id": "g1", "user_id": "web-user", "role": "owner"}]


def test_link_to_same_account_is_noop(db):
    db.tables["users"] = [{"id": "web-user"}]
    _identity(db, "web-user")
    _code(db)

    link_identity(db, "ABC12345", "telegram", "555")

    assert len(db.tables["user_identities"]) == 1
```

- [ ] **Step 2: Rodar e ver falhar** (`ModuleNotFoundError: app.services.identities`).

- [ ] **Step 3: Implementação**

`backend/app/services/user_token.py`:

```python
from datetime import datetime, timedelta, timezone

import jwt

from ..config import settings


def generate_user_token(user_id: str) -> str:
    """JWT (HS256, secret legado do Supabase) para o bot agir em nome do
    usuario na propria API, sob RLS. Vale 24h."""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + timedelta(hours=24),
    }
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")
```

`backend/app/services/identities.py`:

```python
"""Identidades por canal (user_identities). `db` e sempre o client de servico:
quem chama (bot/adaptadores) ainda nao tem sessao de usuario."""
import logging
from datetime import datetime, timezone

from supabase import Client

logger = logging.getLogger("api")


class InvalidLinkCode(Exception):
    """Codigo inexistente, expirado ou ja usado."""


class LinkConflict(Exception):
    """As duas contas ja participam de grupos financeiros diferentes."""


def find_user_by_identity(db: Client, channel: str, external_id: str) -> dict | None:
    identity = (
        db.table("user_identities")
        .select("user_id")
        .eq("channel", channel)
        .eq("external_id", external_id)
        .maybe_single()
        .execute()
    )
    if identity and identity.data:
        user = db.table("users").select("*").eq("id", identity.data["user_id"]).maybe_single().execute()
        return user.data if user else None
    if channel == "telegram":
        return _adopt_legacy_telegram_user(db, external_id)
    return None


def _adopt_legacy_telegram_user(db: Client, external_id: str) -> dict | None:
    """Usuarios criados antes da migration 012 (ou entre ela e o deploy) so tem
    users.telegram_id. Cria a identidade na primeira mensagem. Sai junto com a
    coluna telegram_id."""
    legacy = db.table("users").select("*").eq("telegram_id", int(external_id)).maybe_single().execute()
    if not legacy or not legacy.data:
        return None
    db.table("user_identities").insert(
        {"user_id": legacy.data["id"], "channel": "telegram", "external_id": external_id}
    ).execute()
    return legacy.data


def get_or_create_user(db: Client, channel: str, external_id: str, display_name: str) -> tuple[dict, bool]:
    user = find_user_by_identity(db, channel, external_id)
    if user:
        return user, False

    created = db.table("users").insert({"name": display_name}).execute().data[0]
    try:
        db.table("user_identities").insert(
            {"user_id": created["id"], "channel": channel, "external_id": external_id}
        ).execute()
    except Exception:
        # Duas primeiras mensagens simultaneas: a outra venceu a constraint
        # UNIQUE(channel, external_id). Descarta este usuario e usa o dela.
        db.table("users").delete().eq("id", created["id"]).execute()
        user = find_user_by_identity(db, channel, external_id)
        if user is None:
            raise
        return user, False
    logger.info("Novo usuario %s:%s (%s)", channel, external_id, display_name)
    return created, True


def _group_of(db: Client, user_id: str) -> str | None:
    result = db.table("group_members").select("group_id").eq("user_id", user_id).limit(1).execute()
    return result.data[0]["group_id"] if result.data else None


def link_identity(db: Client, code: str, channel: str, external_id: str) -> None:
    """Liga a identidade do canal a conta web dona do codigo. Se a identidade
    ja pertencia a outro usuario (conta so-bot), funde esse usuario na conta web."""
    now = datetime.now(timezone.utc).isoformat()
    valid = (
        db.table("telegram_link_codes")
        .select("user_id")
        .eq("code", code)
        .is_("used_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not valid.data:
        raise InvalidLinkCode()
    target_id = valid.data[0]["user_id"]

    current = find_user_by_identity(db, channel, external_id)
    old_id = current["id"] if current and current["id"] != target_id else None
    if old_id:
        old_group, target_group = _group_of(db, old_id), _group_of(db, target_id)
        if old_group and target_group and old_group != target_group:
            raise LinkConflict()

    # Reivindica o codigo antes de mexer nos dados: so um consumo vence.
    claimed = (
        db.table("telegram_link_codes")
        .update({"used_at": now})
        .eq("code", code)
        .is_("used_at", "null")
        .execute()
    )
    if not claimed.data:
        raise InvalidLinkCode()

    if current is None:
        db.table("user_identities").insert(
            {"user_id": target_id, "channel": channel, "external_id": external_id}
        ).execute()
    elif old_id:
        _merge_user(db, old_id=old_id, target_id=target_id, target_group=target_group)


def _merge_user(db: Client, old_id: str, target_id: str, target_group: str | None) -> None:
    # Transfere a posse antes de apagar o usuario antigo: groups.owner_id tem
    # ON DELETE CASCADE e apagaria o grupo inteiro com as transacoes.
    db.table("groups").update({"owner_id": target_id}).eq("owner_id", old_id).execute()
    if target_group is None:
        db.table("group_members").update({"user_id": target_id}).eq("user_id", old_id).execute()
    else:
        # Mesmo grupo (o conflito ja foi barrado): so remove a linha duplicada.
        db.table("group_members").delete().eq("user_id", old_id).execute()
    db.table("transactions").update({"user_id": target_id}).eq("user_id", old_id).execute()
    # conversations.user_id e UNIQUE; o historico do bot e efemero, descarta.
    db.table("conversations").delete().eq("user_id", old_id).execute()
    db.table("user_identities").update({"user_id": target_id}).eq("user_id", old_id).execute()
    db.table("users").delete().eq("id", old_id).execute()
```

Remover `app/services/telegram_link.py` e `tests/test_telegram_link_service.py` (`git rm`). O handler ainda importa `telegram_link` até a Task 4; para manter a suíte verde, este passo atualiza o import do handler:

```python
from app.services.identities import InvalidLinkCode, LinkConflict, link_identity
```

e `_link_telegram_account` passa a chamar `link_identity(get_service_supabase(), code, "telegram", str(telegram_id))`, com um `except LinkConflict` que devolve `CONFLICT_LINK_REPLY` (texto na Task 4). Os testes de `/start <código>` trocam o patch para `tgbot.handlers.link_identity` e a asserção para `link.assert_called_once_with(service_db, "ABC12345", "telegram", "123456789")`.

- [ ] **Step 4: Rodar a suíte** (verde).
- [ ] **Step 5: Commit** `feat(identities): identidades por canal e merge de conta sem perda de dados`

---

### Task 3: Rate limit e alerta de limite no núcleo

**Files:**
- Create: `backend/core/__init__.py` (vazio), `backend/core/rate_limit.py`, `backend/core/alerts.py`
- Delete: `backend/tgbot/alerts.py`
- Modify: `backend/agent/tools.py`, `backend/pyproject.toml`
- Test: `backend/tests/test_rate_limit.py`, `backend/tests/test_core_alerts.py`, `backend/tests/test_agent_tools.py`

**Interfaces:**
- Produces: `SlidingWindowLimiter(max_events: int, window_seconds: float, clock=time.monotonic).allow(key: str) -> bool`; `limit_alert_message(category: str, spent: float, monthly_limit: float) -> str | None`; `build_tools(user_token, api_base_url="http://localhost:8000", transport=None, alert_sink: list[str] | None = None)` (sem `bot`/`telegram_id`).

- [ ] **Step 1: Testes que falham**

`backend/tests/test_rate_limit.py`:

```python
from core.rate_limit import SlidingWindowLimiter


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_allows_up_to_max_then_blocks():
    limiter = SlidingWindowLimiter(max_events=3, window_seconds=60, clock=Clock())
    assert [limiter.allow("a") for _ in range(4)] == [True, True, True, False]


def test_window_slides():
    clock = Clock()
    limiter = SlidingWindowLimiter(max_events=2, window_seconds=60, clock=clock)
    limiter.allow("a")
    clock.now = 30
    limiter.allow("a")
    assert not limiter.allow("a")
    clock.now = 61
    assert limiter.allow("a")


def test_keys_are_independent():
    limiter = SlidingWindowLimiter(max_events=1, window_seconds=60, clock=Clock())
    assert limiter.allow("telegram:1")
    assert limiter.allow("telegram:2")
    assert not limiter.allow("telegram:1")
```

`backend/tests/test_core_alerts.py`:

```python
from core.alerts import limit_alert_message


def test_no_alert_below_80_percent():
    assert limit_alert_message("Lazer", 79.0, 100.0) is None


def test_attention_at_80_percent():
    msg = limit_alert_message("Alimentação", 850.0, 1000.0)
    assert msg.startswith("Atenção: 85% do limite mensal de Alimentação")
    assert "R$ 850,00" in msg and "R$ 1.000,00" in msg


def test_alert_at_100_percent():
    msg = limit_alert_message("Lazer", 1200.0, 1000.0)
    assert msg.startswith("ALERTA: O limite mensal de Lazer foi atingido.")


def test_zero_limit_never_alerts():
    assert limit_alert_message("Lazer", 10.0, 0) is None
```

No fim de `backend/tests/test_agent_tools.py`:

```python
@pytest.mark.asyncio
async def test_registrar_transacao_appends_limit_alert_to_sink():
    from fastapi import FastAPI

    api = FastAPI()

    @api.post("/transactions/", status_code=201)
    async def create():
        return {"id": "t1", "date": "2026-10-07"}

    @api.get("/limits/")
    async def limits():
        return [{"category": "Lazer", "spent": 950.0, "monthly_limit": 1000.0, "percent_used": 95}]

    alerts: list[str] = []
    tools = build_tools("tok", "http://internal", transport=httpx.ASGITransport(app=api), alert_sink=alerts)
    registrar = next(t for t in tools if t.__name__ == "registrar_transacao")

    await registrar(amount=50.0, type="expense", category="Lazer")

    assert len(alerts) == 1
    assert "95% do limite mensal de Lazer" in alerts[0]
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/core/rate_limit.py`:

```python
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Limite de eventos por chave numa janela deslizante, em memoria.
    Suficiente para um unico processo (um worker do uvicorn)."""

    def __init__(self, max_events: int, window_seconds: float, clock=time.monotonic):
        self._max = max_events
        self._window = window_seconds
        self._clock = clock
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = self._clock()
        events = self._events[key]
        while events and now - events[0] >= self._window:
            events.popleft()
        if len(events) >= self._max:
            return False
        events.append(now)
        return True
```

`backend/core/alerts.py`:

```python
def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def limit_alert_message(category: str, spent: float, monthly_limit: float) -> str | None:
    """Texto do alerta quando o gasto da categoria atinge 80% ou 100% do limite."""
    if monthly_limit <= 0:
        return None
    percent = (spent / monthly_limit) * 100
    if percent >= 100:
        return (
            f"ALERTA: O limite mensal de {category} foi atingido.\n"
            f"Gasto: {_brl(spent)} | Limite: {_brl(monthly_limit)} (100%)"
        )
    if percent >= 80:
        return (
            f"Atenção: {percent:.0f}% do limite mensal de {category} foi utilizado.\n"
            f"Gasto: {_brl(spent)} | Limite: {_brl(monthly_limit)}"
        )
    return None
```

`backend/agent/tools.py`:

1. Assinatura:

```python
def build_tools(
    user_token: str,
    api_base_url: str = "http://localhost:8000",
    transport: httpx.AsyncBaseTransport | None = None,
    alert_sink: list[str] | None = None,
) -> list:
```

2. Em `registrar_transacao`, o bloco `if response.status_code == 201 and bot and telegram_id:` inteiro vira:

```python
            if response.status_code == 201 and alert_sink is not None:
                limits_response = await client.get("/limits/", headers=headers)
                if limits_response.status_code == 200:
                    for lim in limits_response.json():
                        if lim["category"] == category:
                            alert = limit_alert_message(category, lim["spent"], lim["monthly_limit"])
                            if alert:
                                alert_sink.append(alert)
```

3. Import no topo: `from core.alerts import limit_alert_message`.

`backend/pyproject.toml`: `include = ["app*", "agent*", "tgbot*", "core*"]`.

`git rm tgbot/alerts.py`. No handler, remover `bot=context.bot, telegram_id=telegram_id,` da chamada de `build_tools` (os alertas voltam na Task 4).

- [ ] **Step 4: Rodar a suíte** (verde).
- [ ] **Step 5: Commit** `feat(core): rate limit e alerta de limite sem dependencia do Telegram`

---

### Task 4: Núcleo de conversa e adaptador Telegram

**Files:**
- Create: `backend/core/messages.py`, `backend/core/conversation.py`
- Modify: `backend/tgbot/handlers.py` (reescrito)
- Test: `backend/tests/test_conversation.py` (novo), `backend/tests/test_telegram_handlers.py` (reescrito)

**Interfaces:**
- Consumes: `get_or_create_user`, `link_identity`, `InvalidLinkCode`, `LinkConflict` (Task 2); `generate_user_token` (Task 2); `SlidingWindowLimiter`, `build_tools(..., alert_sink=...)` (Task 3).
- Produces:
  - `core.messages.IncomingMessage(channel: str, external_user_id: str, display_name: str, chat_id: str, text: str)` e `OutgoingMessage(chat_id: str, text: str)`, ambos `@dataclass(frozen=True)`.
  - `core.conversation.process_message(msg, *, api_base_url: str, transport=None) -> list[OutgoingMessage]` (async)
  - `core.conversation.process_start(msg, code: str | None) -> list[OutgoingMessage]`
  - `core.conversation.help_message(msg) -> list[OutgoingMessage]`
  - Constantes `FALLBACK_REPLY`, `RATE_LIMIT_REPLY`, `HELP_TEXT`; `core.conversation.limiter` (instância de módulo, 30 mensagens / 600 s).

- [ ] **Step 1: Testes que falham**

`backend/tests/test_conversation.py`:

```python
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
    assert "vinculado" in out[0].text.lower()


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
```

`backend/tests/test_telegram_handlers.py` (substitui o arquivo):

```python
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
    assert process.call_args.kwargs == {"api_base_url": "http://internal", "transport": "transport"}
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
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/core/messages.py`:

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


@dataclass(frozen=True)
class OutgoingMessage:
    chat_id: str
    text: str
```

`backend/core/conversation.py`:

```python
"""Nucleo de conversa, independente de canal. Adaptadores (tgbot/, e o
WhatsApp na Fase 5) convertem a mensagem do canal em IncomingMessage e enviam
as OutgoingMessage devolvidas."""
import logging

from agent.bot import create_agent
from agent.history import get_history, save_history
from agent.tools import build_tools, is_raw_provider_error, resolve_leaked_tool_call
from app.database import get_service_supabase
from app.services.identities import InvalidLinkCode, LinkConflict, get_or_create_user, link_identity
from app.services.user_token import generate_user_token

from .messages import IncomingMessage, OutgoingMessage
from .rate_limit import SlidingWindowLimiter

logger = logging.getLogger("bot")

FALLBACK_REPLY = "Desculpe, tive um problema para processar sua mensagem. Pode tentar novamente?"
RATE_LIMIT_REPLY = "Você enviou muitas mensagens em pouco tempo. Aguarde alguns minutos e tente novamente."
HELP_TEXT = (
    "Comandos disponíveis:\n\n"
    "/start: iniciar ou reiniciar o assistente\n"
    "/ajuda: exibir esta mensagem\n\n"
    "O que posso fazer por você:\n"
    "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')\n"
    "- Consultar saldo do mês ('Qual meu saldo?')\n"
    "- Ver extrato ('Mostre meus gastos de junho')\n"
    "- Resumo por categoria ('Quanto gastei com alimentação?')\n"
    "- Definir limites ('Limite de R$ 500 para Alimentação')\n"
    "- Ver limites ('Quais são meus limites?')"
)

# Protege a cota do provedor do LLM: 30 mensagens a cada 10 minutos por pessoa.
limiter = SlidingWindowLimiter(max_events=30, window_seconds=600)


def _reply(msg: IncomingMessage, text: str) -> list[OutgoingMessage]:
    return [OutgoingMessage(chat_id=msg.chat_id, text=text)]


def _with_history(history: list[dict], text: str) -> str:
    if not history:
        return f"Usuário: {text}"
    lines = ["", "", "[Histórico recente da conversa:]"]
    for item in history:
        role = "Usuário" if item["role"] == "user" else "Assistente"
        lines.append(f"{role}: {item['content']}")
    lines += ["[Fim do histórico]", "", ""]
    return "\n".join(lines) + f"Usuário: {text}"


async def process_message(msg: IncomingMessage, *, api_base_url: str, transport=None) -> list[OutgoingMessage]:
    who = f"{msg.channel}:{msg.external_user_id}"
    if not limiter.allow(who):
        logger.warning("[%s] Rate limit atingido", who)
        return _reply(msg, RATE_LIMIT_REPLY)

    try:
        db = get_service_supabase()
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        history = get_history(db, user["id"])

        alerts: list[str] = []
        tools = build_tools(
            user_token=generate_user_token(user["id"]),
            api_base_url=api_base_url,
            transport=transport,
            alert_sink=alerts,
        )
        logger.info("[%s] Mensagem recebida: %s", who, msg.text[:80])
        response = await create_agent(tools).arun(_with_history(history[-10:], msg.text))
        reply = response.content if hasattr(response, "content") else str(response)

        leaked = await resolve_leaked_tool_call(reply, tools)
        if leaked is not None:
            logger.warning("[%s] Tool call vazada como texto pelo modelo, executada manualmente", who)
            reply = leaked
        elif is_raw_provider_error(reply):
            logger.warning("[%s] Erro bruto do provedor vazou na resposta, usando fallback", who)
            reply = FALLBACK_REPLY

        history += [{"role": "user", "content": msg.text}, {"role": "assistant", "content": reply}]
        save_history(db, user["id"], history)
    except Exception:
        logger.exception("[%s] Falha ao processar mensagem", who)
        return _reply(msg, FALLBACK_REPLY)

    logger.info("[%s] Resposta: %s", who, reply[:120])
    return _reply(msg, reply) + [OutgoingMessage(chat_id=msg.chat_id, text=a) for a in alerts]


def process_start(msg: IncomingMessage, code: str | None) -> list[OutgoingMessage]:
    db = get_service_supabase()
    if code:
        return _reply(msg, _link(db, msg, code))

    name = msg.display_name or "usuário"
    try:
        _, is_new = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
    except Exception:
        logger.exception("Falha ao registrar %s:%s", msg.channel, msg.external_user_id)
        return _reply(msg, "Não foi possível registrar seu acesso. Por favor, tente novamente.")

    if is_new:
        return _reply(msg, (
            f"Olá, {name}. Bem-vindo ao Assistente Financeiro.\n\n"
            "Para começar, informe suas transações em linguagem natural.\n"
            "Exemplo: 'Gastei R$ 50,00 no mercado hoje'\n\n"
            "Use /ajuda para ver todos os comandos disponíveis."
        ))
    return _reply(msg, (
        f"Bem-vindo de volta, {name}.\n\n"
        "Estou pronto para auxiliá-lo no controle financeiro.\n"
        "Use /ajuda para ver os comandos disponíveis."
    ))


def _link(db, msg: IncomingMessage, code: str) -> str:
    try:
        link_identity(db, code, msg.channel, msg.external_user_id)
    except InvalidLinkCode:
        return "Não foi possível vincular sua conta: código inválido ou expirado."
    except LinkConflict:
        return (
            "Não foi possível vincular: esta conta e a conta do painel já participam de grupos "
            "financeiros diferentes. Saia de um dos grupos e gere um novo código."
        )
    except Exception:
        logger.exception("Falha inesperada ao vincular %s:%s", msg.channel, msg.external_user_id)
        return "Não foi possível vincular sua conta agora. Tente novamente em instantes."
    return (
        "Conta vinculada com sucesso.\n\n"
        "Suas transações e limites agora são os mesmos do painel web."
    )


def help_message(msg: IncomingMessage) -> list[OutgoingMessage]:
    return _reply(msg, HELP_TEXT)
```

`backend/tgbot/handlers.py` (substitui o arquivo):

```python
# -*- coding: utf-8 -*-
"""Adaptador Telegram: converte Update em IncomingMessage, chama o nucleo e
envia as respostas. Sem regra de negocio aqui."""
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from app.config import settings
from core.conversation import help_message, process_message, process_start
from core.messages import IncomingMessage, OutgoingMessage


def _incoming(update: Update) -> IncomingMessage:
    return IncomingMessage(
        channel="telegram",
        external_user_id=str(update.effective_user.id),
        display_name=update.effective_user.first_name or "",
        chat_id=str(update.effective_chat.id),
        text=update.message.text or "",
    )


async def _send(context: ContextTypes.DEFAULT_TYPE, outgoing: list[OutgoingMessage]) -> None:
    for out in outgoing:
        await context.bot.send_message(chat_id=int(out.chat_id), text=out.text)


async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    code = context.args[0] if context.args else None
    await _send(context, process_start(_incoming(update), code))


async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, help_message(_incoming(update)))


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_chat.send_action(ChatAction.TYPING)
    outgoing = await process_message(
        _incoming(update),
        api_base_url=context.bot_data.get("api_base_url", settings.api_base_url),
        transport=context.bot_data.get("api_transport"),
    )
    await _send(context, outgoing)
```

- [ ] **Step 4: Rodar a suíte e o smoke test do webhook** (`scratchpad/smoke_webhook.py` da Fase 1, que exercita `/ajuda` pelo caminho real).
- [ ] **Step 5: Commit** `refactor(bot): nucleo de conversa independente de canal; Telegram vira adaptador`

---

### Task 5: Documentação

- [ ] README: arquitetura cita `core/` e `user_identities`; seção Deploy ganha "Fase 2: aplicar a 012 (pode ser antes do deploy, é aditiva)".
- [ ] PENDENTE: Fase 2 em "Concluido"; nova linha de débito "remover `users.telegram_id` e `_adopt_legacy_telegram_user`".
- [ ] SECURITY: rate limit por usuário no bot implementado (sai de "Baixo").
- [ ] Spec: registrar os ajustes desta fase (sem renomear `telegram_link_codes`, `Notifier` adiado, `chat_type`/`mentions_bot` na Fase 4).
- [ ] Commit `docs: fase 2 (nucleo de canal e identidades)`.
