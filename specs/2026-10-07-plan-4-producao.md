# Fase 1: Produção Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deixar backend e bot prontos para uso por terceiros: sem acesso amplo do role `anon`, aceite de convite seguro, bot rodando dentro da API via webhook e deploy em um único serviço no Render.

**Architecture:** Operações do sistema (bot, preview e aceite de convite) passam a usar um client Supabase com a service_role key; a migration 011 remove todas as policies e grants de `anon`. O python-telegram-bot sobe no lifespan do FastAPI em modo webhook, e as tools do agente chamam a própria API em processo via `httpx.ASGITransport`.

**Tech Stack:** Python 3.12, FastAPI, python-telegram-bot 22, supabase-py 2, httpx, pytest + pytest-asyncio.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 1").

## Global Constraints

- Todos os comandos a partir de `backend/`. Testes: `.venv/bin/pytest -q` (o venv foi criado com `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"`).
- A suíte precisa rodar sem `.env` (o Task 1 adiciona os defaults no `conftest.py`).
- Comentários e mensagens ao usuário em português. Não usar travessão (—) em texto novo.
- `get_supabase(token)` continua sendo o client para operações em nome do usuário. `get_service_supabase()` só em operações do sistema listadas na spec 1.1.
- Um worker do uvicorn em produção.
- Commits com a linha `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/config.py` | Settings: novas variáveis, remove `openai_api_key`, `extra="ignore"` |
| `backend/app/database.py` | `get_service_supabase()` |
| `backend/app/services/telegram_link.py` (novo) | Vínculo de conta Telegram, sem HTTP |
| `backend/app/routers/auth_link.py` | Remove `POST /auth/telegram-link` |
| `backend/app/routers/transactions.py` | `_find_user_group` (sem exceção) |
| `backend/app/routers/groups.py` | Preview e aceite com client de serviço |
| `backend/supabase/migrations/011_revoke_anon_access.sql` (novo) | Remove acesso `anon`, SEC-02 |
| `backend/agent/tools.py` | `transport` injetável |
| `backend/tgbot/handlers.py` | Client de serviço, vínculo direto, transport |
| `backend/tgbot/runner.py` | `build_app(api_base_url, api_transport, webhook)` + polling dev |
| `backend/tgbot/webhook.py` (novo) | Rota do webhook + lifespan |
| `backend/app/main.py` | Lifespan, rota do webhook, CORS das settings |
| `render.yaml` (novo) | Blueprint do Render |
| `README.md`, `PENDENTE.md`, `SECURITY.md`, `backend/.env.example` | Documentação |

---

### Task 1: Settings e client de serviço

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/database.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/.env.example`
- Test: `backend/tests/test_database.py` (novo)

**Interfaces:**
- Produces: `app.database.get_service_supabase() -> supabase.Client` (cacheado com `lru_cache`); `settings.supabase_service_role_key`, `settings.telegram_mode` (`"off" | "webhook" | "polling"`), `settings.public_base_url`, `settings.telegram_webhook_secret`, `settings.api_base_url`, `settings.cors_origins`, `settings.cors_origin_list -> list[str]`.

- [ ] **Step 1: Defaults de teste no conftest**

No topo de `backend/tests/conftest.py`, antes de qualquer import do app:

```python
import os

os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "test-service-key")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-test-secret-test-secret-123")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_database.py`:

```python
from unittest.mock import patch

import pytest

from app import database
from app.config import settings


@pytest.fixture(autouse=True)
def _clear_cache():
    database.get_service_supabase.cache_clear()
    yield
    database.get_service_supabase.cache_clear()


def test_service_client_uses_service_role_key(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-key")
    with patch("app.database.create_client") as create_client:
        database.get_service_supabase()
    create_client.assert_called_once_with(settings.supabase_url, "service-key")


def test_service_client_is_cached(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "service-key")
    with patch("app.database.create_client") as create_client:
        database.get_service_supabase()
        database.get_service_supabase()
    create_client.assert_called_once()


def test_service_client_requires_key(monkeypatch):
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        database.get_service_supabase()


def test_cors_origin_list_splits_and_strips(monkeypatch):
    monkeypatch.setattr(settings, "cors_origins", "https://a.app, https://b.app ,")
    assert settings.cors_origin_list == ["https://a.app", "https://b.app"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_database.py -v`
Expected: FAIL com `AttributeError: module 'app.database' has no attribute 'get_service_supabase'`

- [ ] **Step 4: Implementação**

`backend/app/config.py`:

```python
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: str
    # service_role bypassa RLS: so no backend, nunca no frontend.
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str
    telegram_bot_token: str
    groq_api_key: str = ""

    # "off": API sem bot (testes, dev so da API); "webhook": bot dentro da API
    # (producao); "polling": bot separado via `python -m tgbot.runner` (dev).
    telegram_mode: str = "off"
    # URL publica da API, usada para registrar o webhook. No Render, cai para a
    # RENDER_EXTERNAL_URL injetada automaticamente.
    public_base_url: str = Field(
        default="",
        validation_alias=AliasChoices("PUBLIC_BASE_URL", "RENDER_EXTERNAL_URL"),
    )
    telegram_webhook_secret: str = ""
    # So no modo polling: onde o bot separado encontra a API.
    api_base_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:3000"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


settings = Settings()
```

`backend/app/database.py`:

```python
from functools import lru_cache
from typing import Optional
from supabase import create_client, Client
from .config import settings


def get_supabase(token: Optional[str] = None) -> Client:
    """Cria o client Supabase. Se `token` for passado, repassa o JWT do usuário
    pro PostgREST para que as queries rodem como role `authenticated` (RLS
    avaliando o `auth.uid()` real) em vez de sempre como `anon`."""
    client = create_client(settings.supabase_url, settings.supabase_key)
    if token:
        client.postgrest.auth(token)
    return client


@lru_cache
def get_service_supabase() -> Client:
    """Client com a service_role key, que bypassa RLS. Usar so em operacoes do
    sistema sem usuario logado: bot achando usuario pelo telegram_id, historico
    de conversa, consumo de codigo de vinculo, preview e aceite de convite."""
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY nao configurada no backend.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
```

`backend/.env.example` (substitui o conteúdo):

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-from-supabase-dashboard
TELEGRAM_BOT_TOKEN=123456:ABC-DEF...
GROQ_API_KEY=gsk_...

# off | webhook | polling
TELEGRAM_MODE=off
# Producao (webhook): URL publica da API e segredo do webhook
# Gere o segredo com: python -c "import secrets; print(secrets.token_urlsafe(32))"
PUBLIC_BASE_URL=
TELEGRAM_WEBHOOK_SECRET=
# Dev (polling): onde o bot encontra a API
API_BASE_URL=http://localhost:8000
CORS_ORIGINS=http://localhost:3000
```

- [ ] **Step 5: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam (56 anteriores + 4 novos).

- [ ] **Step 6: Commit**

```bash
git add app/config.py app/database.py tests/conftest.py tests/test_database.py .env.example
git commit -m "feat(backend): client Supabase de servico e novas settings de deploy"
```

---

### Task 2: Vínculo Telegram como serviço e remoção do endpoint público

**Files:**
- Create: `backend/app/services/__init__.py` (vazio)
- Create: `backend/app/services/telegram_link.py`
- Modify: `backend/app/routers/auth_link.py` (remove `TelegramLinkRequest` e `consume_telegram_link_code`)
- Modify: `backend/tgbot/handlers.py` (`_link_telegram_account`, `handle_start`, `handle_message`)
- Modify: `backend/tests/test_auth_link.py` (remove os 3 testes de consumo, adiciona teste de rota removida)
- Create: `backend/tests/test_telegram_link_service.py`
- Modify: `backend/tests/test_telegram_handlers.py`

**Interfaces:**
- Consumes: `get_service_supabase()` (Task 1).
- Produces: `app.services.telegram_link.link_telegram_account(db: Client, code: str, telegram_id: int) -> None`, `InvalidLinkCode(Exception)`. Em `tgbot/handlers.py`, todo acesso ao banco passa por `get_service_supabase()` (o nome `get_supabase` deixa de ser importado ali).

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_telegram_link_service.py`:

```python
from unittest.mock import MagicMock

import pytest

from app.services.telegram_link import InvalidLinkCode, link_telegram_account


def _db_with_code(existing_user=None):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = [
        {"code": "ABC12345", "user_id": "web-user-uuid", "used_at": None}
    ]
    db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = existing_user
    return db


def test_link_sets_telegram_id_and_marks_code_used():
    db = _db_with_code()
    link_telegram_account(db, "ABC12345", 999888777)

    update_payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
    assert {"telegram_id": 999888777} in update_payloads
    assert any("used_at" in p for p in update_payloads)
    db.table.return_value.delete.assert_not_called()


def test_link_rejects_invalid_or_expired_code():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = []
    with pytest.raises(InvalidLinkCode):
        link_telegram_account(db, "BADCODE1", 999888777)


def test_link_merges_existing_bot_only_user():
    db = _db_with_code(existing_user={"id": "bot-only-user-uuid"})
    link_telegram_account(db, "ABC12345", 999888777)

    update_payloads = [c.args[0] for c in db.table.return_value.update.call_args_list]
    assert {"user_id": "web-user-uuid"} in update_payloads
    db.table.return_value.delete.assert_called_once()
```

Em `backend/tests/test_auth_link.py`, apagar `test_consume_telegram_link_code_success`, `test_consume_telegram_link_code_invalid_or_expired` e `test_consume_telegram_link_code_merges_existing_bot_user`, e adicionar:

```python
def test_public_telegram_link_endpoint_was_removed(client):
    response = client.post(
        "/auth/telegram-link",
        json={"code": "ABC12345", "telegram_id": 999888777},
    )
    assert response.status_code == 404
```

Em `backend/tests/test_telegram_handlers.py`, substituir os três testes de `/start <código>` (`..._calls_link_endpoint`, `..._invalid_code_shows_code_error`, `..._server_error_shows_generic_retry`) por:

```python
@pytest.mark.asyncio
async def test_start_command_with_link_code_links_account():
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.first_name = "Lucas"
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["ABC12345"]

    service_db = MagicMock()
    with (
        patch("tgbot.handlers.get_service_supabase", return_value=service_db),
        patch("tgbot.handlers.link_telegram_account") as link,
    ):
        await handle_start(update, context)

    link.assert_called_once_with(service_db, "ABC12345", 123456789)
    reply = update.message.reply_text.call_args[0][0]
    assert "vinculado" in reply.lower()


@pytest.mark.asyncio
async def test_start_command_with_invalid_code_shows_code_error():
    from app.services.telegram_link import InvalidLinkCode
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["EXPIRADO"]

    with (
        patch("tgbot.handlers.get_service_supabase", return_value=MagicMock()),
        patch("tgbot.handlers.link_telegram_account", side_effect=InvalidLinkCode()),
    ):
        await handle_start(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "código inválido ou expirado" in reply.lower()


@pytest.mark.asyncio
async def test_start_command_with_unexpected_error_shows_generic_retry():
    from tgbot.handlers import handle_start

    update = MagicMock()
    update.effective_user.id = 123456789
    update.message.reply_text = AsyncMock()

    context = MagicMock()
    context.args = ["ABC12345"]

    with (
        patch("tgbot.handlers.get_service_supabase", return_value=MagicMock()),
        patch("tgbot.handlers.link_telegram_account", side_effect=RuntimeError("db fora")),
    ):
        await handle_start(update, context)

    reply = update.message.reply_text.call_args[0][0]
    assert "código" not in reply.lower()
    assert "tente novamente" in reply.lower()
```

Ainda em `test_telegram_handlers.py`, trocar todas as ocorrências de `patch("tgbot.handlers.get_supabase", ...)` por `patch("tgbot.handlers.get_service_supabase", ...)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_telegram_link_service.py tests/test_auth_link.py tests/test_telegram_handlers.py -v`
Expected: FAIL (`ModuleNotFoundError: app.services`, rota ainda responde 200/404 conforme o mock, `get_service_supabase` não existe em `tgbot.handlers`).

- [ ] **Step 3: Implementação**

`backend/app/services/telegram_link.py`:

```python
from datetime import datetime, timezone

from supabase import Client


class InvalidLinkCode(Exception):
    """Codigo inexistente, expirado ou ja usado."""


def link_telegram_account(db: Client, code: str, telegram_id: int) -> None:
    """Associa o telegram_id a conta web dona do codigo, migrando grupo,
    transacoes e historico caso esse telegram_id ja tivesse uma identidade de
    bot separada. `db` precisa ser o client de servico: quem chama ainda nao
    tem sessao de usuario."""
    now = datetime.now(timezone.utc).isoformat()

    result = (
        db.table("telegram_link_codes")
        .select("*")
        .eq("code", code)
        .is_("used_at", "null")
        .gte("expires_at", now)
        .execute()
    )
    if not result.data:
        raise InvalidLinkCode()

    target_user_id = result.data[0]["user_id"]

    existing = (
        db.table("users")
        .select("id")
        .eq("telegram_id", telegram_id)
        .maybe_single()
        .execute()
    )
    if existing and existing.data and existing.data["id"] != target_user_id:
        old_user_id = existing.data["id"]
        for table in ("group_members", "transactions", "conversations"):
            db.table(table).update({"user_id": target_user_id}).eq("user_id", old_user_id).execute()
        db.table("users").delete().eq("id", old_user_id).execute()

    db.table("users").update({"telegram_id": telegram_id}).eq("id", target_user_id).execute()
    db.table("telegram_link_codes").update({"used_at": now}).eq("code", code).execute()
```

`backend/app/routers/auth_link.py`: apagar a classe `TelegramLinkRequest` e a função `consume_telegram_link_code` inteiras (do `class TelegramLinkRequest` até o fim do arquivo). Remover `HTTPException` do import do FastAPI se não for mais usado.

`backend/tgbot/handlers.py`:

1. Imports: remover `import httpx`; trocar `from app.database import get_supabase` por:

```python
from app.database import get_service_supabase
from app.services.telegram_link import InvalidLinkCode, link_telegram_account
```

2. Substituir `_link_telegram_account` por:

```python
def _link_telegram_account(telegram_id: int, code: str) -> str:
    try:
        link_telegram_account(get_service_supabase(), code, telegram_id)
    except InvalidLinkCode:
        return "Não foi possível vincular sua conta: código inválido ou expirado."
    except Exception:
        logger.exception("Falha inesperada ao vincular telegram_id=%s", telegram_id)
        return "Não foi possível vincular sua conta agora. Tente novamente em instantes."
    return (
        "Telegram vinculado à sua conta com sucesso.\n\n"
        "Suas transações e limites agora são os mesmos do painel web."
    )
```

3. Em `handle_start`, o bloco `if context.args:` vira:

```python
    if context.args:
        await update.message.reply_text(_link_telegram_account(telegram_id, context.args[0]))
        return
```

4. Em `handle_start` e `handle_message`, `db = get_supabase()` vira `db = get_service_supabase()`.

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add app/services app/routers/auth_link.py tgbot/handlers.py tests/test_telegram_link_service.py tests/test_auth_link.py tests/test_telegram_handlers.py
git commit -m "refactor(bot): vinculo Telegram vira servico interno e endpoint publico sai"
```

---

### Task 3: Preview e aceite de convite com client de serviço

**Files:**
- Modify: `backend/app/routers/transactions.py` (`_find_user_group`)
- Modify: `backend/app/routers/groups.py` (`get_invite_preview`, `accept_invite`)
- Modify: `backend/tests/test_groups.py`

**Interfaces:**
- Consumes: `get_service_supabase()` (Task 1).
- Produces: `app.routers.transactions._find_user_group(db: Client, user_id: str) -> str | None`. `_get_user_group` mantém a assinatura e o 404.

- [ ] **Step 1: Write the failing tests**

Em `backend/tests/test_groups.py`, substituir `test_accept_invite_valid_token`, `test_accept_invite_invalid_token`, `test_get_invite_preview_success` e `test_get_invite_preview_not_found` por:

```python
def _user_db(existing_group=None):
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = (
        [{"group_id": existing_group}] if existing_group else []
    )
    return db


def test_accept_invite_valid_token(client, valid_token):
    user_db = _user_db()
    service_db = MagicMock()
    service_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value.data = [
        {"id": "invite-uuid", "group_id": "group-uuid-456"}
    ]

    with (
        patch("app.routers.groups.get_supabase", return_value=user_db),
        patch("app.routers.groups.get_service_supabase", return_value=service_db),
    ):
        response = client.post(
            "/groups/accept",
            params={"token": "valid-token-abc"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Convite aceito com sucesso"
    user_db.table.return_value.upsert.assert_called_once()
    service_db.table.return_value.insert.assert_called_once_with(
        {"group_id": "group-uuid-456", "user_id": "user-uuid-123", "role": "member"}
    )


def test_accept_invite_invalid_or_used_token(client, valid_token):
    service_db = MagicMock()
    service_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute.return_value.data = []

    with (
        patch("app.routers.groups.get_supabase", return_value=_user_db()),
        patch("app.routers.groups.get_service_supabase", return_value=service_db),
    ):
        response = client.post(
            "/groups/accept",
            params={"token": "invalid-token-xyz"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 404
    service_db.table.return_value.insert.assert_not_called()


def test_accept_invite_rejects_user_already_in_group(client, valid_token):
    service_db = MagicMock()

    with (
        patch("app.routers.groups.get_supabase", return_value=_user_db(existing_group="other-group")),
        patch("app.routers.groups.get_service_supabase", return_value=service_db),
    ):
        response = client.post(
            "/groups/accept",
            params={"token": "valid-token-abc"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 409
    service_db.table.return_value.update.assert_not_called()


def test_get_invite_preview_success(client):
    service_db = MagicMock()
    service_db.table.return_value.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value.data = {
        "email": "familiar@example.com",
        "group_id": "group-uuid-456",
    }
    service_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "name": "Família Silva",
    }

    with patch("app.routers.groups.get_service_supabase", return_value=service_db):
        response = client.get("/groups/invite/abc-token-123")

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "familiar@example.com"
    assert body["group_name"] == "Família Silva"


def test_get_invite_preview_not_found(client):
    service_db = MagicMock()
    service_db.table.return_value.select.return_value.eq.return_value.is_.return_value.maybe_single.return_value.execute.return_value.data = None

    with patch("app.routers.groups.get_service_supabase", return_value=service_db):
        response = client.get("/groups/invite/token-invalido")

    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_groups.py -v`
Expected: FAIL com `AttributeError: ... does not have the attribute 'get_service_supabase'`.

- [ ] **Step 3: Implementação**

`backend/app/routers/transactions.py`, substituir `_get_user_group` por:

```python
def _find_user_group(db: Client, user_id: str) -> str | None:
    result = (
        db.table("group_members")
        .select("group_id")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0]["group_id"] if result.data else None


def _get_user_group(db: Client, user_id: str) -> str:
    group_id = _find_user_group(db, user_id)
    if group_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuário não pertence a nenhum grupo. Crie um grupo ou aceite um convite.",
        )
    return group_id
```

`backend/app/routers/groups.py`:

1. Imports:

```python
from ..database import get_service_supabase, get_supabase
from ..routers.transactions import _ensure_user_profile, _find_user_group, _get_user_group
```

2. Em `get_invite_preview`, docstring e client:

```python
    """Endpoint publico: quem recebeu o link de convite ainda nao tem conta.
    Roda com o client de servico porque o role anon nao le mais invites/groups
    (migration 011); so devolve email e nome do grupo de um token valido."""
    db = get_service_supabase()
```

3. Substituir `accept_invite` inteiro por:

```python
@router.post("/accept")
async def accept_invite(
    token: str = Query(...),
    user: dict = Depends(get_current_user),
):
    db = get_supabase(user["token"])
    _ensure_user_profile(db, user)
    if _find_user_group(db, user["id"]) is not None:
        raise HTTPException(status_code=409, detail="Você já participa de um grupo financeiro.")

    # Reivindica o convite num unico UPDATE condicional: so um aceite vence,
    # mesmo com duas requisicoes simultaneas para o mesmo token. Roda como
    # servico porque o usuario nao tem permissao de UPDATE em invites (SEC-02).
    service = get_service_supabase()
    claimed = (
        service.table("invites")
        .update({"accepted_at": datetime.now(timezone.utc).isoformat()})
        .eq("token", token)
        .is_("accepted_at", "null")
        .execute()
    )
    if not claimed.data:
        raise HTTPException(status_code=404, detail="Convite inválido ou já utilizado")

    service.table("group_members").insert({
        "group_id": claimed.data[0]["group_id"],
        "user_id": user["id"],
        "role": "member",
    }).execute()
    return {"message": "Convite aceito com sucesso"}
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add app/routers/transactions.py app/routers/groups.py tests/test_groups.py
git commit -m "fix(groups): aceite de convite atomico via client de servico (SEC-02)"
```

---

### Task 4: Migration 011 removendo acesso do role anon

**Files:**
- Create: `backend/supabase/migrations/011_revoke_anon_access.sql`
- Test: `backend/tests/test_migrations.py` (novo)

**Interfaces:**
- Consumes: Tasks 2 e 3 (nenhum caminho de código depende mais de `anon`).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_migrations.py`:

```python
import re
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parent.parent / "supabase" / "migrations"
REVOKE_FILE = "011_revoke_anon_access.sql"


def _sql(name: str) -> str:
    return (MIGRATIONS / name).read_text(encoding="utf-8")


def _anon_policies_before_011() -> set[str]:
    policies = set()
    for path in sorted(MIGRATIONS.glob("*.sql")):
        if path.name >= REVOKE_FILE:
            continue
        for name, body in re.findall(r'CREATE POLICY "(\w+)"(.*?);', path.read_text(encoding="utf-8"), re.S):
            if re.search(r"\bTO\s+anon\b", body):
                policies.add(name)
    return policies


def _dropped_in_011() -> set[str]:
    return set(re.findall(r'DROP POLICY IF EXISTS "(\w+)"', _sql(REVOKE_FILE)))


def test_every_anon_policy_is_dropped():
    anon = _anon_policies_before_011()
    assert anon, "esperava encontrar policies TO anon nas migrations antigas"
    assert anon <= _dropped_in_011()


def test_sec02_policies_are_dropped():
    assert {"invites_accept_update", "group_members_insert_self"} <= _dropped_in_011()


def test_anon_grants_are_revoked_on_app_tables():
    sql = _sql(REVOKE_FILE)
    for table in (
        "users", "conversations", "groups", "group_members", "transactions",
        "category_limits", "invites", "telegram_link_codes",
    ):
        assert re.search(rf"REVOKE ALL ON public\.{table} FROM anon;", sql), table
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_migrations.py -v`
Expected: FAIL com `FileNotFoundError` para `011_revoke_anon_access.sql`.

- [ ] **Step 3: Implementação**

`backend/supabase/migrations/011_revoke_anon_access.sql`:

```sql
-- SEC-01 e SEC-02 (ver SECURITY.md).
--
-- As migrations 002 a 010 deram ao role anon policies USING (true) para o bot
-- operar sem sessao de usuario. Como a anon key e publica (fica no bundle do
-- frontend), isso expunha todas as tabelas. Agora o backend usa a service_role
-- key para essas operacoes (app/database.py::get_service_supabase), entao o
-- role anon perde todo acesso as tabelas do app.
--
-- Tambem remove:
-- - invites_accept_update (001): qualquer autenticado marcava qualquer convite
--   como aceito. O aceite agora roda como servico depois de validar o token.
-- - group_members_insert_self (001): qualquer autenticado se inseria em
--   qualquer grupo. O insert do dono ao criar grupo segue coberto por
--   group_members_owner_all (005); o do convidado roda como servico.

DROP POLICY IF EXISTS "users_bot_read" ON public.users;
DROP POLICY IF EXISTS "users_bot_insert" ON public.users;
DROP POLICY IF EXISTS "users_bot_update" ON public.users;
DROP POLICY IF EXISTS "users_bot_delete" ON public.users;
DROP POLICY IF EXISTS "conversations_bot_all" ON public.conversations;
DROP POLICY IF EXISTS "telegram_link_codes_bot_all" ON public.telegram_link_codes;
DROP POLICY IF EXISTS "group_members_bot_all" ON public.group_members;
DROP POLICY IF EXISTS "transactions_bot_all" ON public.transactions;
DROP POLICY IF EXISTS "invites_bot_select" ON public.invites;
DROP POLICY IF EXISTS "groups_bot_select" ON public.groups;

DROP POLICY IF EXISTS "invites_accept_update" ON public.invites;
DROP POLICY IF EXISTS "group_members_insert_self" ON public.group_members;

REVOKE ALL ON public.users FROM anon;
REVOKE ALL ON public.conversations FROM anon;
REVOKE ALL ON public.groups FROM anon;
REVOKE ALL ON public.group_members FROM anon;
REVOKE ALL ON public.transactions FROM anon;
REVOKE ALL ON public.category_limits FROM anon;
REVOKE ALL ON public.invites FROM anon;
REVOKE ALL ON public.telegram_link_codes FROM anon;
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/011_revoke_anon_access.sql tests/test_migrations.py
git commit -m "fix(db): remove acesso do role anon e policies de convite abertas (SEC-01, SEC-02)"
```

---

### Task 5: Tools do agente com transport injetável

**Files:**
- Modify: `backend/agent/tools.py`
- Modify: `backend/tgbot/handlers.py` (chamada de `build_tools`)
- Test: `backend/tests/test_agent_tools.py`

**Interfaces:**
- Produces: `build_tools(user_token: str, api_base_url: str = "http://localhost:8000", bot=None, telegram_id=None, transport: httpx.AsyncBaseTransport | None = None) -> list`. O handler lê `context.bot_data.get("api_transport")`.

- [ ] **Step 1: Write the failing test**

No fim de `backend/tests/test_agent_tools.py`:

```python
@pytest.mark.asyncio
async def test_tools_call_api_in_process_via_transport():
    from fastapi import FastAPI, Request

    api = FastAPI()
    seen = {}

    @api.get("/limits/")
    async def limits(request: Request):
        seen["auth"] = request.headers.get("authorization")
        return []

    tools = build_tools("fake-token", "http://internal", transport=httpx.ASGITransport(app=api))
    consultar = next(t for t in tools if t.__name__ == "consultar_limites")

    result = await consultar()

    assert "Nenhum limite configurado" in result
    assert seen["auth"] == "Bearer fake-token"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_agent_tools.py::test_tools_call_api_in_process_via_transport -v`
Expected: FAIL com `TypeError: build_tools() got an unexpected keyword argument 'transport'`.

- [ ] **Step 3: Implementação**

Em `backend/agent/tools.py`:

1. Assinatura e helper logo no início de `build_tools`:

```python
def build_tools(
    user_token: str,
    api_base_url: str = "http://localhost:8000",
    bot=None,
    telegram_id=None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> list:
    headers = {"Authorization": f"Bearer {user_token}"}

    def _client() -> httpx.AsyncClient:
        # Com transport (bot dentro da API), as chamadas vao direto para o app
        # FastAPI em processo, sem rede; sem ele, vao por HTTP para api_base_url.
        return httpx.AsyncClient(base_url=api_base_url, transport=transport, timeout=30)
```

2. Trocar cada `async with httpx.AsyncClient() as client:` por `async with _client() as client:` (6 ocorrências).
3. Trocar cada URL `f"{api_base_url}/..."` pelo caminho relativo: `"/transactions/"`, `"/limits/"`, `"/groups/"`, `"/summary/"`. Em `consultar_extrato`, manter os `params` como estão e usar `"/transactions/"`.

Em `backend/tgbot/handlers.py`, a chamada de `build_tools` vira:

```python
    tools = build_tools(
        user_token=user_token,
        api_base_url=context.bot_data.get("api_base_url", settings.api_base_url),
        bot=context.bot,
        telegram_id=telegram_id,
        transport=context.bot_data.get("api_transport"),
    )
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam (os testes antigos fazem patch de `httpx.AsyncClient` e não dependem da URL).

- [ ] **Step 5: Commit**

```bash
git add agent/tools.py tgbot/handlers.py tests/test_agent_tools.py
git commit -m "feat(agent): tools aceitam transport para chamar a API em processo"
```

---

### Task 6: Bot dentro da API via webhook

**Files:**
- Modify: `backend/tgbot/runner.py`
- Create: `backend/tgbot/webhook.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_telegram_webhook.py` (novo)

**Interfaces:**
- Consumes: `build_tools(..., transport=...)` via `bot_data["api_transport"]` (Task 5); settings da Task 1.
- Produces: `tgbot.runner.build_app(api_base_url: str, api_transport: httpx.AsyncBaseTransport | None = None, webhook: bool = False) -> telegram.ext.Application`; `tgbot.webhook.router` (APIRouter com `POST /telegram/webhook`); `tgbot.webhook.telegram_lifespan(api: FastAPI)` (asynccontextmanager); `tgbot.webhook.WEBHOOK_PATH = "/telegram/webhook"`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/test_telegram_webhook.py`:

```python
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.config import settings

SECRET = "segredo-de-teste"


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)


@pytest.fixture
def fake_ptb():
    ptb = MagicMock()
    ptb.update_queue = asyncio.Queue()
    return ptb


def test_webhook_rejects_wrong_secret(client, webhook_secret, fake_ptb):
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "errado"},
    )
    assert response.status_code == 403
    assert fake_ptb.update_queue.qsize() == 0


def test_webhook_rejects_when_secret_not_configured(client, monkeypatch, fake_ptb):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": ""},
    )
    assert response.status_code == 403


def test_webhook_returns_503_when_bot_not_running(client, webhook_secret):
    client.app.state.telegram_app = None
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 503


def test_webhook_enqueues_update(client, webhook_secret, fake_ptb):
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 42},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200
    assert fake_ptb.update_queue.get_nowait().update_id == 42


@pytest.mark.asyncio
async def test_lifespan_off_does_not_start_bot(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "off")
    api = FastAPI()
    with patch("tgbot.webhook.build_app") as build_app:
        async with telegram_lifespan(api):
            assert api.state.telegram_app is None
    build_app.assert_not_called()


@pytest.mark.asyncio
async def test_lifespan_webhook_registers_and_stops(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "webhook")
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.com/")
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)

    ptb = MagicMock()
    ptb.initialize = AsyncMock()
    ptb.start = AsyncMock()
    ptb.stop = AsyncMock()
    ptb.shutdown = AsyncMock()
    ptb.bot.set_webhook = AsyncMock()

    api = FastAPI()
    with patch("tgbot.webhook.build_app", return_value=ptb) as build_app:
        async with telegram_lifespan(api):
            assert api.state.telegram_app is ptb

    assert build_app.call_args.kwargs["webhook"] is True
    assert build_app.call_args.kwargs["api_transport"] is not None
    ptb.bot.set_webhook.assert_awaited_once_with(
        url="https://api.example.com/telegram/webhook",
        secret_token=SECRET,
        allowed_updates=["message"],
    )
    ptb.stop.assert_awaited_once()
    ptb.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_webhook_requires_url_and_secret(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "webhook")
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)

    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        async with telegram_lifespan(FastAPI()):
            pass


def test_build_app_webhook_has_no_updater():
    from tgbot.runner import build_app

    ptb = build_app(api_base_url="http://internal", webhook=True)
    assert ptb.updater is None
    assert ptb.bot_data["api_base_url"] == "http://internal"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_telegram_webhook.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'tgbot.webhook'` e 404 na rota.

- [ ] **Step 3: Implementação**

`backend/tgbot/runner.py` (substitui o arquivo):

```python
# -*- coding: utf-8 -*-
import httpx
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .handlers import handle_start, handle_help, handle_message
from app.config import settings


def build_app(
    api_base_url: str,
    api_transport: httpx.AsyncBaseTransport | None = None,
    webhook: bool = False,
) -> Application:
    # concurrent_updates: uma resposta lenta do LLM nao trava os outros usuarios.
    builder = Application.builder().token(settings.telegram_bot_token).concurrent_updates(8)
    if webhook:
        # Em webhook os updates chegam pela rota do FastAPI (tgbot/webhook.py),
        # nao ha polling.
        builder = builder.updater(None)
    app = builder.build()

    app.bot_data["api_base_url"] = api_base_url
    app.bot_data["api_transport"] = api_transport

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ajuda", handle_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main():
    """Modo polling, so para desenvolvimento local. Use um bot de dev separado:
    o polling apaga o webhook registrado no bot de producao."""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = build_app(api_base_url=settings.api_base_url)
    logging.getLogger("bot").info("Bot iniciado em modo polling. API em %s", settings.api_base_url)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
```

Observação: o `load_dotenv()` antigo sai porque `Settings` já lê o `.env`.

`backend/tgbot/webhook.py`:

```python
# -*- coding: utf-8 -*-
import hmac
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import APIRouter, FastAPI, HTTPException, Request
from telegram import Update

from app.config import settings
from .runner import build_app

logger = logging.getLogger("bot")

WEBHOOK_PATH = "/telegram/webhook"
# Host ficticio: com ASGITransport as tools chamam o app em processo.
INTERNAL_API_BASE_URL = "http://internal"

router = APIRouter(tags=["telegram"])


@router.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    received = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    expected = settings.telegram_webhook_secret
    if not expected or not hmac.compare_digest(received, expected):
        raise HTTPException(status_code=403, detail="Segredo do webhook inválido.")

    ptb = getattr(request.app.state, "telegram_app", None)
    if ptb is None:
        raise HTTPException(status_code=503, detail="Bot não está ativo.")

    # Enfileira e responde na hora: o processamento (LLM) roda em background
    # na Application, entao o Telegram nao estoura timeout nem reenvia.
    update = Update.de_json(await request.json(), ptb.bot)
    await ptb.update_queue.put(update)
    return {"ok": True}


@asynccontextmanager
async def telegram_lifespan(api: FastAPI):
    if settings.telegram_mode != "webhook":
        api.state.telegram_app = None
        yield
        return

    if not settings.public_base_url:
        raise RuntimeError("TELEGRAM_MODE=webhook exige PUBLIC_BASE_URL (ou RENDER_EXTERNAL_URL).")
    if not settings.telegram_webhook_secret:
        raise RuntimeError("TELEGRAM_MODE=webhook exige TELEGRAM_WEBHOOK_SECRET.")

    ptb = build_app(
        api_base_url=INTERNAL_API_BASE_URL,
        api_transport=httpx.ASGITransport(app=api),
        webhook=True,
    )
    await ptb.initialize()
    url = f"{settings.public_base_url.rstrip('/')}{WEBHOOK_PATH}"
    await ptb.bot.set_webhook(
        url=url,
        secret_token=settings.telegram_webhook_secret,
        allowed_updates=["message"],
    )
    await ptb.start()
    api.state.telegram_app = ptb
    logger.info("Bot ativo em modo webhook: %s", url)
    try:
        yield
    finally:
        await ptb.stop()
        await ptb.shutdown()
        api.state.telegram_app = None
```

`backend/app/main.py`: importar e ligar lifespan e rota.

```python
from tgbot.webhook import router as telegram_router, telegram_lifespan
```

```python
app = FastAPI(title="my-finance-bot API", version="0.1.0", lifespan=telegram_lifespan)
```

e, junto dos outros routers:

```python
app.include_router(telegram_router)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam.

- [ ] **Step 5: Smoke test local do lifespan em modo off**

Run: `timeout 5 .venv/bin/uvicorn app.main:app --port 8765 & sleep 3; curl -s localhost:8765/health; wait`
(com as variáveis do `conftest.py` exportadas no shell)
Expected: `{"status":"ok"}` e nenhum erro de startup.

- [ ] **Step 6: Commit**

```bash
git add tgbot/runner.py tgbot/webhook.py app/main.py tests/test_telegram_webhook.py
git commit -m "feat(bot): bot roda dentro da API via webhook do Telegram"
```

---

### Task 7: CORS restrito às origens configuradas

**Files:**
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_cors.py` (novo)

**Interfaces:**
- Consumes: `settings.cors_origin_list` (Task 1).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_cors.py`:

```python
def _preflight(client, origin):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_cors_allows_configured_origin(client):
    response = _preflight(client, "http://localhost:3000")
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocks_unknown_origin(client):
    response = _preflight(client, "https://site-malicioso.example")
    assert "access-control-allow-origin" not in response.headers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_cors.py -v`
Expected: `test_cors_blocks_unknown_origin` FAIL (hoje `allow_origins=["*"]`).

- [ ] **Step 3: Implementação**

Em `backend/app/main.py`, importar `from .config import settings` e trocar o middleware por:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Run tests**

Run: `.venv/bin/pytest -q`
Expected: todos passam.

- [ ] **Step 5: Commit**

```bash
git add app/main.py tests/test_cors.py
git commit -m "fix(api): CORS restrito as origens de CORS_ORIGINS (CORS-01)"
```

---

### Task 8: Blueprint do Render e documentação

**Files:**
- Create: `render.yaml` (raiz do repo)
- Modify: `README.md`, `PENDENTE.md`, `SECURITY.md`

- [ ] **Step 1: `render.yaml`**

```yaml
services:
  - type: web
    name: finncy-api
    runtime: python
    rootDir: backend
    plan: free
    buildCommand: pip install .
    # Um worker so: cada worker teria sua propria Application do Telegram.
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 1
    healthCheckPath: /health
    envVars:
      - key: PYTHON_VERSION
        value: "3.12.7"
      - key: TELEGRAM_MODE
        value: webhook
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_KEY
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: SUPABASE_JWT_SECRET
        sync: false
      - key: TELEGRAM_BOT_TOKEN
        sync: false
      - key: TELEGRAM_WEBHOOK_SECRET
        sync: false
      - key: GROQ_API_KEY
        sync: false
      - key: CORS_ORIGINS
        sync: false
```

`TELEGRAM_WEBHOOK_SECRET` não usa `generateValue` do Render porque o valor gerado pode conter `+`, `/` e `=`, e o Telegram só aceita `A-Z a-z 0-9 _ -`. Gerar com `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

- [ ] **Step 2: README.md**

- Arquitetura: bot e API no mesmo processo; Telegram chega por `POST /telegram/webhook`.
- Seção "Configuração/Backend": listar as variáveis do novo `.env.example` com uma linha de explicação cada.
- Seção "Rodando localmente": API com `uvicorn app.main:app --reload` (`TELEGRAM_MODE=off`) e bot com `python -m tgbot.runner` (`TELEGRAM_MODE` ignorado, usa polling com `API_BASE_URL`), avisando para usar bot de dev separado.
- Nova seção "Deploy". A migration 011 só pode ser aplicada **depois** que o código novo estiver no ar, porque o código antigo depende do role anon. Ordem: 1) configurar `SUPABASE_SERVICE_ROLE_KEY` e demais variáveis no Render, 2) deploy do backend, 3) aplicar a 011, 4) Vercel com `NEXT_PUBLIC_API_URL` apontando para o Render, 5) `CORS_ORIGINS` com o domínio da Vercel. Mencionar hibernação do plano free.
- Testes: `uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -e ".[dev]"` e `.venv/bin/pytest`.

- [ ] **Step 3: PENDENTE.md e SECURITY.md**

- PENDENTE: mover SEC-01, SEC-02, CORS-01, OPENAI-01 e a parte de código do DEPLOY-01 para "Concluido" (Fase 1); deixar "DEPLOY-01: executar o deploy" pendente; remover BOT-01; apontar para `specs/2026-10-07-producao-e-familia-design.md` como roteiro das próximas fases.
- SECURITY: itens 1, 2 e 4 para "Já corrigido", citando migration 011, `get_service_supabase` e `CORS_ORIGINS`; adicionar `group_members_insert_self` como corrigido; no item 5 registrar que a service_role key tem o mesmo nível de privilégio que o JWT secret; no item 3 registrar que o endpoint público `/auth/telegram-link` não existe mais.

- [ ] **Step 4: Verificação final**

Run: `.venv/bin/pytest -q && grep -rn "get_supabase()" app tgbot agent`
Expected: todos os testes passam e o grep não encontra chamadas sem token (todo acesso sem usuário usa `get_service_supabase()`).

- [ ] **Step 5: Commit**

```bash
git add render.yaml README.md PENDENTE.md SECURITY.md
git commit -m "docs: deploy no Render com bot via webhook e atualizacao de seguranca"
```
