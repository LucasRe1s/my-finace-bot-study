# Fase 3: Família no privado Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A família consegue usar o bot só pelo Telegram: convite por link do bot, entrada no grupo sem cadastro na web, nomes reais em vez de ids e um jeito de desfazer o último lançamento.

**Architecture:** Regras de convite e de membros viram serviços (`app/services/invites.py`, `app/services/membership.py`) usados tanto pela API web quanto pelo núcleo do bot. O núcleo (`core/conversation.py`) ganha o fluxo `/start join_<token>` e o comando `/convidar`; o link é montado por uma função que o adaptador do canal fornece (`invite_link`), porque o formato do link depende do canal.

**Tech Stack:** Python 3.12, FastAPI, supabase-py 2, python-telegram-bot 22, Next.js, pytest.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 3").

## Global Constraints

- Comandos do backend a partir de `backend/`; testes com `.venv/bin/pytest -q`. Frontend: `npx tsc --noEmit` em `frontend/`.
- Comentários e mensagens em português; sem travessão (—) em texto novo.
- Acesso sem usuário logado só via `get_service_supabase()`.
- Payload de deep link do Telegram: até 64 caracteres `[A-Za-z0-9_-]`. `join_` + UUID (36) = 41.
- Commits com `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisões desta fase

- **Qualquer membro do grupo pode gerar convite** (comportamento atual da API web). A spec dizia "o dono"; numa família restringir ao dono só atrapalha. Mudar depois é trocar uma checagem.
- **Convites expiram em 7 dias** (`invites.expires_at`, default no banco). Hoje não expiram, e um link de Telegram encaminhado ficaria válido para sempre.
- **`invites.email` passa a ser opcional** (convite do bot não tem email) e, quando informado, é validado como email (resolve P1-T4).
- **Nome exibido:** `users.name`. Usuários web nascem com o email como nome; quando a pessoa fala com o bot, o nome do Telegram substitui um nome vazio ou com `@`. `_ensure_user_profile` deixa de sobrescrever o nome a cada requisição.
- **Desfazer:** só a última transação **do próprio usuário** criada nos últimos 10 minutos.

## Bug corrigido no caminho

`Transaction.user_id` é `str` no modelo de resposta, mas a coluna é `ON DELETE SET NULL`. Depois que um usuário é apagado (por exemplo, no merge de contas), o extrato do grupo responderia 500. Passa a ser `str | None`.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/supabase/migrations/013_invites_expiry_optional_email.sql` (novo) | `email` opcional, `expires_at` |
| `backend/app/services/membership.py` (novo) | `find_user_group`, `names_by_id`, `group_name` |
| `backend/app/services/invites.py` (novo) | `create_invite`, `accept_invite`, exceções |
| `backend/app/routers/groups.py` | Usa os serviços; membros com nome |
| `backend/app/routers/transactions.py` | `user_name` no extrato; `POST /transactions/undo-last` |
| `backend/app/models/group.py`, `transaction.py` | `EmailStr` opcional; `user_id` opcional, `user_name` |
| `backend/app/services/identities.py` | Usa `find_user_group`; atualiza nome placeholder |
| `backend/agent/tools.py` | `desfazer_ultima_transacao`, `gerar_convite`, nome no extrato |
| `backend/agent/prompts.py` | Fluxos de desfazer e convite |
| `backend/core/conversation.py` | `/start join_<token>`, `invite_command`, `invite_link` |
| `backend/tgbot/handlers.py`, `runner.py` | `/convidar`, `invite_link` do Telegram |
| `backend/tests/fakes.py` | `in_` e `order` |
| `frontend/src/lib/api.ts`, `components/transaction-table.tsx`, `app/dashboard/family/page.tsx`, `app/convite/[token]/page.tsx` | Nomes, coluna "Quem", convite sem email |

---

### Task 1: Serviços de membros e convites, migration 013

**Files:**
- Create: `backend/supabase/migrations/013_invites_expiry_optional_email.sql`, `backend/app/services/membership.py`, `backend/app/services/invites.py`
- Modify: `backend/tests/fakes.py`, `backend/app/routers/transactions.py`, `backend/app/routers/groups.py`, `backend/app/services/identities.py`, `backend/app/models/group.py`, `backend/pyproject.toml`
- Test: `backend/tests/test_invites.py` (novo), `backend/tests/test_migrations.py`, `backend/tests/test_groups.py`, `backend/tests/test_fakes.py`

**Interfaces:**
- Produces:
  - `membership.find_user_group(db, user_id: str) -> str | None`
  - `membership.names_by_id(db, user_ids: list[str | None]) -> dict[str, str]`
  - `membership.group_name(db, group_id: str) -> str`
  - `invites.create_invite(db, group_id: str, invited_by: str, email: str | None = None) -> dict | None`
  - `invites.accept_invite(db, token: str, user_id: str) -> str` (devolve `group_id`; levanta `InviteNotFound` ou `AlreadyInGroup`)
  - `FakeSupabase` ganha `.in_(column, values)` e `.order(column, desc=False)`.

- [ ] **Step 1: Testes que falham**

`tests/test_fakes.py`, acrescentar:

```python
def test_in_and_order():
    db = FakeSupabase()
    db.tables["t"] = [{"id": "a", "n": 2}, {"id": "b", "n": 3}, {"id": "c", "n": 1}]
    rows = db.table("t").select("*").in_("id", ["a", "c"]).order("n", desc=True).execute().data
    assert [r["id"] for r in rows] == ["a", "c"]
```

`tests/test_migrations.py`, acrescentar:

```python
def test_invites_email_optional_and_expiring():
    sql = _sql("013_invites_expiry_optional_email.sql")
    assert "ALTER COLUMN email DROP NOT NULL" in sql
    assert re.search(r"ADD COLUMN expires_at TIMESTAMPTZ NOT NULL DEFAULT \(NOW\(\) \+ INTERVAL '7 days'\)", sql)
```

`tests/test_invites.py`:

```python
from datetime import datetime, timedelta, timezone

import pytest

from app.services.invites import AlreadyInGroup, InviteNotFound, accept_invite, create_invite
from app.services.membership import group_name, names_by_id
from tests.fakes import FakeSupabase

FUTURE = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
PAST = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()


@pytest.fixture
def db():
    fake = FakeSupabase()
    fake.tables["groups"] = [{"id": "g1", "name": "Família Silva"}]
    fake.tables["invites"] = [{"id": "i1", "group_id": "g1", "token": "tok", "accepted_at": None, "expires_at": FUTURE}]
    return fake


def test_accept_adds_member_and_marks_invite(db):
    assert accept_invite(db, "tok", "u1") == "g1"
    assert db.tables["group_members"] == [{"id": db.tables["group_members"][0]["id"], "group_id": "g1", "user_id": "u1", "role": "member"}]
    assert db.tables["invites"][0]["accepted_at"] is not None


def test_accept_is_single_use(db):
    accept_invite(db, "tok", "u1")
    with pytest.raises(InviteNotFound):
        accept_invite(db, "tok", "u2")


def test_accept_rejects_expired(db):
    db.tables["invites"][0]["expires_at"] = PAST
    with pytest.raises(InviteNotFound):
        accept_invite(db, "tok", "u1")


def test_accept_rejects_user_already_in_group(db):
    db.tables["group_members"] = [{"id": "m", "group_id": "outro", "user_id": "u1", "role": "owner"}]
    with pytest.raises(AlreadyInGroup):
        accept_invite(db, "tok", "u1")
    assert db.tables["invites"][0]["accepted_at"] is None


def test_create_invite_without_email(db):
    invite = create_invite(db, "g1", "u1")
    assert invite["group_id"] == "g1" and invite["invited_by"] == "u1" and invite["email"] is None


def test_names_by_id_ignores_missing_and_none():
    db = FakeSupabase()
    db.tables["users"] = [{"id": "u1", "name": "Ana"}, {"id": "u2", "name": None}]
    assert names_by_id(db, ["u1", "u2", None, "u3"]) == {"u1": "Ana", "u2": ""}
    assert names_by_id(db, []) == {}


def test_group_name_fallback():
    db = FakeSupabase()
    assert group_name(db, "nao-existe") == "grupo financeiro"
```

Em `tests/test_groups.py`, substituir `test_accept_invite_valid_token`, `test_accept_invite_invalid_or_used_token`, `test_accept_invite_rejects_user_already_in_group`, `test_get_invite_preview_success` e `test_get_invite_preview_not_found` (e o helper `_user_db`) por:

```python
from datetime import datetime, timedelta, timezone

from tests.fakes import FakeSupabase

_FUTURE = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


def _service_db():
    db = FakeSupabase()
    db.tables["groups"] = [{"id": "group-uuid-456", "name": "Família Silva"}]
    db.tables["invites"] = [{
        "id": "invite-uuid", "group_id": "group-uuid-456", "token": "valid-token-abc",
        "email": "familiar@example.com", "accepted_at": None, "expires_at": _FUTURE,
    }]
    return db


def _accept(client, valid_token, service_db, token="valid-token-abc"):
    user_db = MagicMock()
    with (
        patch("app.routers.groups.get_supabase", return_value=user_db),
        patch("app.routers.groups.get_service_supabase", return_value=service_db),
    ):
        response = client.post(
            "/groups/accept",
            params={"token": token},
            headers={"Authorization": f"Bearer {valid_token}"},
        )
    return response, user_db


def test_accept_invite_valid_token(client, valid_token):
    service_db = _service_db()
    response, user_db = _accept(client, valid_token, service_db)

    assert response.status_code == 200
    assert response.json()["message"] == "Convite aceito com sucesso"
    user_db.table.return_value.upsert.assert_called_once()
    assert service_db.tables["group_members"][0]["user_id"] == "user-uuid-123"


def test_accept_invite_invalid_or_used_token(client, valid_token):
    response, _ = _accept(client, valid_token, _service_db(), token="invalid-token-xyz")
    assert response.status_code == 404


def test_accept_invite_rejects_user_already_in_group(client, valid_token):
    service_db = _service_db()
    service_db.tables["group_members"] = [{"id": "m", "group_id": "other", "user_id": "user-uuid-123", "role": "owner"}]
    response, _ = _accept(client, valid_token, service_db)
    assert response.status_code == 409
    assert service_db.tables["invites"][0]["accepted_at"] is None


def test_get_invite_preview_success(client):
    with patch("app.routers.groups.get_service_supabase", return_value=_service_db()):
        response = client.get("/groups/invite/valid-token-abc")
    assert response.status_code == 200
    assert response.json() == {"email": "familiar@example.com", "group_name": "Família Silva"}


def test_get_invite_preview_expired(client):
    service_db = _service_db()
    service_db.tables["invites"][0]["expires_at"] = "2020-01-01T00:00:00+00:00"
    with patch("app.routers.groups.get_service_supabase", return_value=service_db):
        response = client.get("/groups/invite/valid-token-abc")
    assert response.status_code == 404


def test_get_invite_preview_not_found(client):
    with patch("app.routers.groups.get_service_supabase", return_value=_service_db()):
        response = client.get("/groups/invite/token-invalido")
    assert response.status_code == 404


def test_send_invite_without_email(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [
        {"id": "i1", "group_id": "group-uuid-456", "email": None, "token": "tok"}
    ]
    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.post("/groups/invite", json={}, headers={"Authorization": f"Bearer {valid_token}"})
    assert response.status_code == 201
    assert mock_db.table.return_value.insert.call_args.args[0]["email"] is None


def test_send_invite_rejects_invalid_email(client, valid_token):
    response = client.post(
        "/groups/invite", json={"email": "nao-e-email"}, headers={"Authorization": f"Bearer {valid_token}"}
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/supabase/migrations/013_invites_expiry_optional_email.sql`:

```sql
-- Fase 3: convite pelo bot do Telegram.
--
-- email opcional: o convite gerado no bot nao tem email (o link vai direto
-- para o familiar). Validado como email na API quando informado.
-- expires_at: convites passam a valer 7 dias. Antes nao expiravam, e um link
-- encaminhado ficaria valido para sempre. Convites antigos ganham 7 dias a
-- partir da aplicacao desta migration.

ALTER TABLE public.invites ALTER COLUMN email DROP NOT NULL;
ALTER TABLE public.invites ADD COLUMN expires_at TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '7 days');
```

`backend/tests/fakes.py`, em `_Query`:

```python
    def in_(self, column, values):
        allowed = set(values)
        self._filters.append(lambda row: row.get(column) in allowed)
        return self

    def order(self, column, desc=False):
        self._order = (column, desc)
        return self
```

com `self._order = None` no `__init__` e, no ramo `select` de `execute`, antes do `[: self._limit]`:

```python
            if self._order:
                column, desc = self._order
                matched = sorted(matched, key=lambda row: row.get(column), reverse=desc)
```

`backend/app/services/membership.py`:

```python
from supabase import Client


def find_user_group(db: Client, user_id: str) -> str | None:
    result = db.table("group_members").select("group_id").eq("user_id", user_id).limit(1).execute()
    return result.data[0]["group_id"] if result.data else None


def names_by_id(db: Client, user_ids: list[str | None]) -> dict[str, str]:
    """Nome de cada usuario. Chamar com o client de servico, so com ids que ja
    vieram de uma consulta feita sob RLS (membros/transacoes do grupo)."""
    ids = sorted({uid for uid in user_ids if uid})
    if not ids:
        return {}
    result = db.table("users").select("id, name").in_("id", ids).execute()
    return {row["id"]: row.get("name") or "" for row in result.data or []}


def group_name(db: Client, group_id: str) -> str:
    result = db.table("groups").select("name").eq("id", group_id).maybe_single().execute()
    return result.data["name"] if result and result.data else "grupo financeiro"
```

`backend/app/services/invites.py`:

```python
from datetime import datetime, timezone

from supabase import Client

from .membership import find_user_group


class InviteNotFound(Exception):
    """Convite inexistente, expirado ou ja usado."""


class AlreadyInGroup(Exception):
    """O usuario ja participa de um grupo financeiro."""


def create_invite(db: Client, group_id: str, invited_by: str, email: str | None = None) -> dict | None:
    result = db.table("invites").insert({"group_id": group_id, "invited_by": invited_by, "email": email}).execute()
    return result.data[0] if result.data else None


def accept_invite(db: Client, token: str, user_id: str) -> str:
    """Coloca o usuario no grupo do convite e devolve o group_id. `db` e o
    client de servico: o usuario nao tem permissao de UPDATE em invites."""
    if find_user_group(db, user_id) is not None:
        raise AlreadyInGroup()

    now = datetime.now(timezone.utc).isoformat()
    # UPDATE condicional: so um aceite vence, mesmo com requisicoes simultaneas.
    claimed = (
        db.table("invites")
        .update({"accepted_at": now})
        .eq("token", token)
        .is_("accepted_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not claimed.data:
        raise InviteNotFound()

    group_id = claimed.data[0]["group_id"]
    db.table("group_members").insert({"group_id": group_id, "user_id": user_id, "role": "member"}).execute()
    return group_id
```

`backend/app/routers/transactions.py`: apagar a função `_find_user_group` e importar no lugar dela:

```python
from ..services.membership import find_user_group as _find_user_group
```

`backend/app/services/identities.py`: apagar `_group_of`, importar `from .membership import find_user_group` e trocar as duas chamadas `_group_of(db, ...)` por `find_user_group(db, ...)`.

`backend/app/models/group.py`:

```python
from pydantic import BaseModel, EmailStr


class InviteCreate(BaseModel):
    # Opcional: convites gerados no bot nao tem email.
    email: EmailStr | None = None
```

(`InviteResponse` não é usado em lugar nenhum e sai.)

`backend/pyproject.toml`: adicionar `"email-validator>=2.0",` às dependências.

`backend/app/routers/groups.py`:

1. Imports:

```python
from ..services.invites import AlreadyInGroup, InviteNotFound, accept_invite as accept_invite_service, create_invite
from ..services.membership import group_name, names_by_id
from ..routers.transactions import _ensure_user_profile, _get_user_group
```

2. `invite_member`:

```python
    db = get_supabase(user["token"])
    group_id = _get_user_group(db, user["id"])
    invite = create_invite(db, group_id, user["id"], data.email)
    if invite is None:
        raise HTTPException(status_code=500, detail="Erro ao criar convite. Tente novamente.")
    return invite
```

3. `get_invite_preview`, corpo:

```python
    db = get_service_supabase()
    invite = (
        db.table("invites")
        .select("email, group_id")
        .eq("token", token)
        .is_("accepted_at", "null")
        .gte("expires_at", datetime.now(timezone.utc).isoformat())
        .maybe_single()
        .execute()
    )
    if not invite or not invite.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")
    return {"email": invite.data["email"], "group_name": group_name(db, invite.data["group_id"])}
```

4. `accept_invite` (rota):

```python
    db = get_supabase(user["token"])
    _ensure_user_profile(db, user)
    try:
        accept_invite_service(get_service_supabase(), token, user["id"])
    except AlreadyInGroup:
        raise HTTPException(status_code=409, detail="Você já participa de um grupo financeiro.")
    except InviteNotFound:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")
    return {"message": "Convite aceito com sucesso"}
```

- [ ] **Step 4:** `uv pip install --python .venv/bin/python -e ".[dev]"` (por causa do `email-validator`) e rodar a suíte.
- [ ] **Step 5: Commit** `feat(invites): convites com validade de 7 dias, email opcional e servico compartilhado`

---

### Task 2: Nomes de quem lança e de quem participa

**Files:**
- Modify: `backend/app/routers/transactions.py`, `backend/app/routers/groups.py`, `backend/app/models/transaction.py`, `backend/app/services/identities.py`, `backend/agent/tools.py`
- Test: `backend/tests/test_transactions.py`, `backend/tests/test_groups.py`, `backend/tests/test_identities.py`, `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `names_by_id` (Task 1).
- Produces: `GET /groups/members` -> `[{user_id, role, name}]`; `GET /transactions/` -> cada item com `user_name: str | None`; `Transaction.user_id: str | None`.

- [ ] **Step 1: Testes que falham**

`tests/test_transactions.py`, substituir `test_list_transactions` por:

```python
def test_list_transactions_includes_author_name(client, valid_token):
    user_db = MagicMock()
    user_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    base = {"amount": 50.0, "type": "expense", "category": "Alimentação", "description": "Mercado",
            "date": "2026-06-25", "group_id": "group-uuid-456", "created_at": "2026-06-25T10:00:00"}
    user_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {**base, "id": "t1", "user_id": "user-uuid-123"},
        {**base, "id": "t2", "user_id": None},
    ]
    service_db = FakeSupabase()
    service_db.tables["users"] = [{"id": "user-uuid-123", "name": "Ana"}]

    with (
        patch("app.routers.transactions.get_supabase", return_value=user_db),
        patch("app.routers.transactions.get_service_supabase", return_value=service_db),
    ):
        response = client.get("/transactions/", headers={"Authorization": f"Bearer {valid_token}"})

    assert response.status_code == 200
    assert [t["user_name"] for t in response.json()] == ["Ana", None]
```

(com `from tests.fakes import FakeSupabase` no topo).

`tests/test_groups.py`, substituir `test_list_members` por:

```python
def test_list_members_with_names(client, valid_token):
    user_db = MagicMock()
    user_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    user_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"user_id": "user-uuid-123", "role": "owner"},
        {"user_id": "user-uuid-456", "role": "member"},
    ]
    service_db = FakeSupabase()
    service_db.tables["users"] = [{"id": "user-uuid-123", "name": "Ana"}, {"id": "user-uuid-456", "name": "Bia"}]

    with (
        patch("app.routers.groups.get_supabase", return_value=user_db),
        patch("app.routers.groups.get_service_supabase", return_value=service_db),
    ):
        response = client.get("/groups/members", headers={"Authorization": f"Bearer {valid_token}"})

    assert response.status_code == 200
    assert response.json() == [
        {"user_id": "user-uuid-123", "role": "owner", "name": "Ana"},
        {"user_id": "user-uuid-456", "role": "member", "name": "Bia"},
    ]
```

`tests/test_identities.py`, acrescentar:

```python
def test_bot_name_replaces_email_placeholder(db):
    db.tables["users"] = [{"id": "u1", "name": "ana@x.com"}]
    _identity(db, "u1")

    user, _ = get_or_create_user(db, "telegram", "555", "Ana")

    assert user["name"] == "Ana"
    assert db.tables["users"][0]["name"] == "Ana"


def test_bot_name_does_not_override_real_name(db):
    db.tables["users"] = [{"id": "u1", "name": "Ana Paula"}]
    _identity(db, "u1")

    user, _ = get_or_create_user(db, "telegram", "555", "Aninha")

    assert user["name"] == "Ana Paula"
```

`tests/test_agent_tools.py`, acrescentar:

```python
@pytest.mark.asyncio
async def test_consultar_extrato_shows_author():
    from fastapi import FastAPI

    api = FastAPI()

    @api.get("/transactions/")
    async def listar():
        return [{"amount": 50.0, "type": "expense", "category": "Lazer", "description": "Cinema",
                 "date": "2026-10-07", "user_name": "Bia"}]

    tools = build_tools("tok", "http://internal", transport=httpx.ASGITransport(app=api))
    extrato = next(t for t in tools if t.__name__ == "consultar_extrato")

    assert "Cinema | 2026-10-07 | Bia" in await extrato()
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`app/models/transaction.py`, em `Transaction`:

```python
class Transaction(TransactionCreate):
    id: str
    # NULL quando o autor foi apagado (FK ON DELETE SET NULL).
    user_id: Optional[str] = None
    user_name: Optional[str] = None
    group_id: str
    created_at: str
```

`app/routers/transactions.py`:

1. `from ..database import get_service_supabase, get_supabase` e `from ..services.membership import find_user_group as _find_user_group, names_by_id`.
2. Fim de `list_transactions`:

```python
    rows = query.order("date", desc=True).execute().data or []
    names = names_by_id(get_service_supabase(), [t.get("user_id") for t in rows])
    return [{**t, "user_name": names.get(t.get("user_id"))} for t in rows]
```

3. `_ensure_user_profile`: acrescentar `ignore_duplicates=True` ao `upsert` e trocar a docstring final por "... Nao sobrescreve o nome de quem ja existe."

`app/routers/groups.py`, fim de `list_members`:

```python
    rows = db.table("group_members").select("user_id, role").eq("group_id", group_id).execute().data or []
    names = names_by_id(get_service_supabase(), [r["user_id"] for r in rows])
    return [{**r, "name": names.get(r["user_id"], "")} for r in rows]
```

`app/services/identities.py`, em `get_or_create_user`, o retorno do usuário existente vira:

```python
    user = find_user_by_identity(db, channel, external_id)
    if user:
        # Conta web nasce com o email como nome; o nome do canal e melhor.
        current = user.get("name") or ""
        if display_name and (not current or "@" in current):
            db.table("users").update({"name": display_name}).eq("id", user["id"]).execute()
            user = {**user, "name": display_name}
        return user, False
```

`agent/tools.py`, no laço de `consultar_extrato`:

```python
        for t in transactions[:20]:
            tipo = "+" if t["type"] == "income" else "-"
            autor = f" | {t['user_name']}" if t.get("user_name") else ""
            lines.append(f"  {tipo} {_fmt_brl(t['amount'])} | {t['category']} | {t['description']} | {t['date']}{autor}")
```

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `feat: nomes de membros e de quem lancou cada transacao`

---

### Task 3: Desfazer o último lançamento

**Files:**
- Modify: `backend/app/routers/transactions.py`, `backend/agent/tools.py`, `backend/agent/prompts.py`
- Test: `backend/tests/test_transactions.py`, `backend/tests/test_agent_tools.py`

**Interfaces:**
- Produces: `POST /transactions/undo-last` -> 200 com a transação apagada, 404 se não houver; tool `desfazer_ultima_transacao()`.

- [ ] **Step 1: Testes que falham**

`tests/test_transactions.py`:

```python
def _tx(id, user_id, minutes_ago):
    created = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": id, "user_id": user_id, "group_id": "g1", "amount": 10.0, "type": "expense",
            "category": "Lazer", "description": "x", "date": "2026-10-07", "created_at": created}


def _undo(client, valid_token, db):
    with patch("app.routers.transactions.get_supabase", return_value=db):
        return client.post("/transactions/undo-last", headers={"Authorization": f"Bearer {valid_token}"})


def test_undo_last_deletes_most_recent_own_transaction(client, valid_token):
    db = FakeSupabase()
    db.tables["transactions"] = [_tx("old", "user-uuid-123", 5), _tx("new", "user-uuid-123", 1), _tx("other", "user-uuid-999", 0)]

    response = _undo(client, valid_token, db)

    assert response.status_code == 200
    assert response.json()["id"] == "new"
    assert [t["id"] for t in db.tables["transactions"]] == ["old", "other"]


def test_undo_last_ignores_transactions_older_than_10_minutes(client, valid_token):
    db = FakeSupabase()
    db.tables["transactions"] = [_tx("old", "user-uuid-123", 11)]

    response = _undo(client, valid_token, db)

    assert response.status_code == 404
    assert len(db.tables["transactions"]) == 1
```

(com `from datetime import datetime, timedelta, timezone` no topo).

`tests/test_agent_tools.py`:

```python
@pytest.mark.asyncio
async def test_desfazer_ultima_transacao():
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    api = FastAPI()
    state = {"calls": 0}

    @api.post("/transactions/undo-last")
    async def undo():
        state["calls"] += 1
        if state["calls"] == 1:
            return {"amount": 50.0, "type": "expense", "category": "Lazer", "description": "Cinema"}
        return JSONResponse({"detail": "nada"}, status_code=404)

    tools = build_tools("tok", "http://internal", transport=httpx.ASGITransport(app=api))
    desfazer = next(t for t in tools if t.__name__ == "desfazer_ultima_transacao")

    assert await desfazer() == "Transação desfeita: Despesa de R$ 50,00 em Lazer (Cinema)."
    assert "nos últimos 10 minutos" in await desfazer()
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`app/routers/transactions.py` (imports `from datetime import datetime, timedelta, timezone`):

```python
UNDO_WINDOW_MINUTES = 10


@router.post("/undo-last", response_model=Transaction)
async def undo_last_transaction(user: dict = Depends(get_current_user)):
    """Apaga a ultima transacao do proprio usuario criada nos ultimos 10 min."""
    db = get_supabase(user["token"])
    since = (datetime.now(timezone.utc) - timedelta(minutes=UNDO_WINDOW_MINUTES)).isoformat()
    result = (
        db.table("transactions")
        .select("*")
        .eq("user_id", user["id"])
        .gte("created_at", since)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhuma transação sua nos últimos {UNDO_WINDOW_MINUTES} minutos.",
        )
    tx = result.data[0]
    db.table("transactions").delete().eq("id", tx["id"]).execute()
    return tx
```

`agent/tools.py`, nova tool (e incluída na lista de retorno):

```python
    async def desfazer_ultima_transacao() -> str:
        """Desfaz (apaga) a última transação registrada pelo próprio usuário nos últimos 10 minutos.
        Use somente depois que o usuário confirmar."""
        async with _client() as client:
            response = await client.post("/transactions/undo-last", headers=headers)
        if response.status_code == 200:
            tx = response.json()
            tipo = "Receita" if tx["type"] == "income" else "Despesa"
            descricao = tx.get("description") or "sem descrição"
            return f"Transação desfeita: {tipo} de {_fmt_brl(tx['amount'])} em {tx['category']} ({descricao})."
        if response.status_code == 404:
            return "Não há transação sua registrada nos últimos 10 minutos para desfazer."
        return f"Erro ao desfazer transação: {response.text}"
```

`agent/prompts.py`, nova seção antes de "## Erros":

```
## Desfazer lançamento
- Se o usuário pedir para desfazer, cancelar ou apagar o último lançamento, pergunte: "Confirma que deseja desfazer seu último lançamento? (Sim/Não)"
- Somente após confirmação explícita, chame desfazer_ultima_transacao e repasse o resultado
- Só é possível desfazer lançamentos do próprio usuário feitos nos últimos 10 minutos
```

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `feat: desfazer o ultimo lancamento pelo bot`

---

### Task 4: Convite e entrada no grupo pelo bot

**Files:**
- Modify: `backend/agent/tools.py`, `backend/agent/prompts.py`, `backend/core/conversation.py`, `backend/tgbot/handlers.py`, `backend/tgbot/runner.py`
- Test: `backend/tests/test_conversation.py`, `backend/tests/test_telegram_handlers.py`, `backend/tests/test_agent_tools.py`

**Interfaces:**
- Consumes: `create_invite`, `accept_invite`, `InviteNotFound`, `AlreadyInGroup`, `find_user_group`, `group_name` (Task 1).
- Produces: `build_tools(..., invite_link: Callable[[str], str] | None = None)` com a tool `gerar_convite()`; `process_message(msg, *, api_base_url, transport=None, invite_link=None)`; `process_start` trata `join_<token>`; `invite_command(msg, invite_link) -> list[OutgoingMessage]`; `JOIN_PREFIX = "join_"`; handler `handle_invite` e `CommandHandler("convidar")`.

- [ ] **Step 1: Testes que falham**

`tests/test_conversation.py`, acrescentar:

```python
from datetime import datetime, timedelta, timezone

from core.conversation import invite_command

LINK = lambda token: f"https://t.me/finncyBot?start=join_{token}"  # noqa: E731
_FUTURE = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()


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
```

Observação: o `FakeSupabase` gera `token` só se o teste não passar um; em `test_invite_command_returns_link`, `create_invite` não envia `token` (o banco gera via default). Para o fake se comportar como o banco, `FakeSupabase` aceita defaults por tabela: `FakeSupabase(defaults={"invites": lambda: {"token": str(uuid4())}})`, e a fixture `db` de `test_conversation.py` passa esse default. Implementar no `__init__` (`self._defaults = defaults or {}`) e no `insert` (`row = {"id": str(uuid4()), **self._db.default_row(self._table), **item}`), com:

```python
    def default_row(self, table: str) -> dict:
        factory = self._defaults.get(table)
        return factory() if factory else {}
```

A fixture vira:

```python
@pytest.fixture
def db(monkeypatch):
    fake = FakeSupabase(
        unique={"user_identities": [("channel", "external_id")]},
        defaults={"invites": lambda: {"token": str(uuid4()), "accepted_at": None, "expires_at": _FUTURE}},
    )
    monkeypatch.setattr(conversation, "get_service_supabase", lambda: fake)
    return fake
```

(com `from uuid import uuid4` e `_FUTURE` definidos antes da fixture).

`tests/test_telegram_handlers.py`, acrescentar e ajustar:

```python
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
```

e, em `test_message_is_converted_and_replies_are_sent`, a asserção dos kwargs vira:

```python
    kwargs = process.call_args.kwargs
    assert kwargs["api_base_url"] == "http://internal" and kwargs["transport"] == "transport"
    assert kwargs["invite_link"]("abc").endswith("?start=join_abc")
```

`tests/test_agent_tools.py`:

```python
@pytest.mark.asyncio
async def test_gerar_convite_returns_channel_link():
    from fastapi import FastAPI

    api = FastAPI()

    @api.post("/groups/invite", status_code=201)
    async def invite():
        return {"token": "abc"}

    tools = build_tools("tok", "http://internal", transport=httpx.ASGITransport(app=api),
                        invite_link=lambda t: f"https://t.me/finncyBot?start=join_{t}")
    gerar = next(t for t in tools if t.__name__ == "gerar_convite")

    assert "https://t.me/finncyBot?start=join_abc" in await gerar()


@pytest.mark.asyncio
async def test_gerar_convite_without_channel_link():
    tools = build_tools("tok", "http://internal")
    gerar = next(t for t in tools if t.__name__ == "gerar_convite")
    assert "painel web" in await gerar()
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`agent/tools.py`:

1. `from typing import Callable` e o parâmetro `invite_link: Callable[[str], str] | None = None` em `build_tools`.
2. Nova tool (incluída na lista de retorno):

```python
    async def gerar_convite() -> str:
        """Gera um link de convite (uso único, válido por 7 dias) para um familiar entrar no grupo financeiro."""
        if invite_link is None:
            return "Este canal ainda não gera links de convite. Gere o convite pelo painel web."
        async with _client() as client:
            response = await client.post("/groups/invite", json={}, headers=headers)
        if response.status_code == 201:
            link = invite_link(response.json()["token"])
            return f"Convite criado. Envie este link ao familiar (uso único, válido por 7 dias):\n{link}"
        return f"Erro ao gerar convite: {response.text}"
```

`agent/prompts.py`, nova seção antes de "## Erros":

```
## Convidar familiar
- Se o usuário quiser convidar alguém para o grupo, chame gerar_convite
- Repasse o link exatamente como a tool devolveu, sem alterar nenhum caractere
- Quem receber o link entra no grupo ao abri-lo, sem precisar de cadastro
```

`core/conversation.py`:

1. Imports:

```python
from typing import Callable

from app.services.invites import AlreadyInGroup, InviteNotFound, accept_invite, create_invite
from app.services.membership import find_user_group, group_name
```

2. Constantes e `HELP_TEXT` (substitui o anterior):

```python
JOIN_PREFIX = "join_"
HELP_TEXT = (
    "Comandos disponíveis:\n\n"
    "/start: iniciar ou reiniciar o assistente\n"
    "/convidar: gerar link de convite para um familiar\n"
    "/ajuda: exibir esta mensagem\n\n"
    "O que posso fazer por você:\n"
    "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')\n"
    "- Desfazer o último lançamento ('Desfaz o último')\n"
    "- Consultar saldo do mês ('Qual meu saldo?')\n"
    "- Ver extrato ('Mostre meus gastos de junho')\n"
    "- Resumo por categoria ('Quanto gastei com alimentação?')\n"
    "- Definir limites ('Limite de R$ 500 para Alimentação')\n"
    "- Ver limites ('Quais são meus limites?')"
)
```

3. `process_message` ganha `invite_link: Callable[[str], str] | None = None` e repassa `invite_link=invite_link` ao `build_tools`.

4. Em `process_start`, logo após `db = get_service_supabase()`:

```python
    if code and code.startswith(JOIN_PREFIX):
        return _reply(msg, _join(db, msg, code[len(JOIN_PREFIX):]))
```

5. Novas funções:

```python
def _join(db, msg: IncomingMessage, token: str) -> str:
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group_id = accept_invite(db, token, user["id"])
    except InviteNotFound:
        return "Convite inválido, expirado ou já utilizado. Peça um novo link a quem convidou você."
    except AlreadyInGroup:
        return "Você já participa de um grupo financeiro e não pode entrar em outro."
    except Exception:
        logger.exception("Falha ao entrar no grupo %s:%s", msg.channel, msg.external_user_id)
        return "Não foi possível entrar no grupo agora. Tente novamente em instantes."
    return (
        f"Você entrou no grupo {group_name(db, group_id)}.\n\n"
        "Agora é só me contar seus gastos e receitas, por exemplo: 'Gastei R$ 50,00 no mercado'.\n"
        "Use /ajuda para ver tudo o que posso fazer."
    )


def invite_command(msg: IncomingMessage, invite_link: Callable[[str], str]) -> list[OutgoingMessage]:
    db = get_service_supabase()
    try:
        user, _ = get_or_create_user(db, msg.channel, msg.external_user_id, msg.display_name)
        group_id = find_user_group(db, user["id"])
        if group_id is None:
            return _reply(msg, (
                "Você ainda não tem um grupo financeiro. "
                "Diga 'criar grupo' para criar um e depois use /convidar."
            ))
        invite = create_invite(db, group_id, user["id"])
    except Exception:
        logger.exception("Falha ao gerar convite %s:%s", msg.channel, msg.external_user_id)
        return _reply(msg, "Não foi possível gerar o convite agora. Tente novamente em instantes.")
    return _reply(msg, (
        "Envie este link ao familiar (uso único, válido por 7 dias):\n"
        f"{invite_link(invite['token'])}"
    ))
```

`tgbot/handlers.py`:

```python
from core.conversation import help_message, invite_command, process_message, process_start


def _invite_link(context: ContextTypes.DEFAULT_TYPE):
    username = context.bot.username
    return lambda token: f"https://t.me/{username}?start=join_{token}"


async def handle_invite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await _send(context, invite_command(_incoming(update), _invite_link(context)))
```

e `handle_message` passa `invite_link=_invite_link(context)` ao `process_message`.

`tgbot/runner.py`: importar `handle_invite` e registrar `app.add_handler(CommandHandler("convidar", handle_invite))`.

- [ ] **Step 4: Rodar a suíte e o smoke test do webhook.**
- [ ] **Step 5: Commit** `feat(bot): convite por link do Telegram e entrada no grupo sem cadastro web`

---

### Task 5: Frontend

**Files:**
- Modify: `frontend/src/lib/api.ts`, `frontend/src/components/transaction-table.tsx`, `frontend/src/app/dashboard/family/page.tsx`, `frontend/src/app/convite/[token]/page.tsx`

- [ ] **Step 1: Tipos em `api.ts`**

```ts
export type Transaction = {
  id: string;
  amount: number;
  type: "income" | "expense";
  category: string;
  description: string;
  date: string;
  created_at: string;
  user_id: string | null;
  user_name: string | null;
};
```

```ts
export type GroupMember = {
  user_id: string;
  role: "owner" | "member";
  name: string;
};
```

```ts
export type InvitePreview = {
  email: string | null;
  group_name: string;
};
```

e o retorno de `sendInvite` com `email: string | null`.

- [ ] **Step 2: Coluna "Quem" na tabela** (`transaction-table.tsx`): `<TableHead>Quem</TableHead>` depois de "Descrição" e `<TableCell className="text-gray-500">{t.user_name || "-"}</TableCell>` na mesma posição.

- [ ] **Step 3: Família** (`family/page.tsx`): no lugar do id truncado,

```tsx
              <span className="text-sm text-gray-700">
                {m.name || `${m.user_id.slice(0, 8)}...`}
              </span>
```

e o texto do card de convite:

```tsx
          <p className="text-sm text-gray-500 mb-4">
            Gere um link para adicionar um familiar ao grupo. Pelo Telegram é
            mais simples: mande /convidar para o bot e envie o link que ele
            devolver. Quem abrir o link entra no grupo sem precisar de cadastro.
          </p>
```

- [ ] **Step 4: Convite sem email** (`convite/[token]/page.tsx`): estado `const [email, setEmail] = useState("");`; usar `const inviteEmail = preview?.email ?? email;` no `signUp`/`signInWithPassword`; quando `preview.email` for `null`, renderizar um campo de email obrigatório antes do de senha:

```tsx
            {!preview.email && (
              <div className="space-y-1">
                <Label htmlFor="email">Seu email</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
              </div>
            )}
```

- [ ] **Step 5:** `npx tsc --noEmit` sem erros.
- [ ] **Step 6: Commit** `feat(frontend): nomes dos membros, autor no extrato e convite sem email`

---

### Task 6: Documentação

- [ ] README: funcionalidades do Telegram ganham `/convidar`, entrada por link e desfazer; seção Deploy cita a migration 013 (aditiva).
- [ ] PENDENTE: Fase 3 em "Concluido"; P1-T4 e P3-T6 saem dos débitos.
- [ ] Spec: Fase 3 aponta para este plano e registra as decisões (qualquer membro convida, validade de 7 dias).
- [ ] Commit `docs: fase 3 (familia no privado)`.
