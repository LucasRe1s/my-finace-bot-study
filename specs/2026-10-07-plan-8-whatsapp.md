# Fase 5: Adaptador WhatsApp Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cada pessoa da família consegue usar o bot pelo WhatsApp no privado, com as mesmas funções do Telegram (registrar, consultar, limites, desfazer, convite, vínculo com a conta web), rodando em paralelo ao Telegram.

**Architecture:** Novo adaptador `wabot/` sobre o mesmo núcleo `core/`. O webhook da Cloud API da Meta chega em `/whatsapp/webhook` na própria API: `GET` faz a verificação do `hub.challenge`, `POST` confere a assinatura `X-Hub-Signature-256`, descarta reentregas, responde 200 na hora e processa em background. Como o WhatsApp não tem comandos nativos, um roteador de texto traduz `/start <código>`, `join_<token>`, `/ajuda` e `/convidar` para as funções do núcleo. As respostas saem pela Graph API.

**Tech Stack:** Python 3.12, FastAPI, httpx, WhatsApp Cloud API (Graph API `v26.0`, configurável), pytest.

**Spec:** `specs/2026-10-07-producao-e-familia-design.md` (seção "Fase 5").

## Global Constraints

- Comandos a partir de `backend/`; testes com `.venv/bin/pytest -q`.
- Comentários e mensagens em português; sem travessão (—) em texto novo.
- O canal fica **desligado** se faltar qualquer uma das variáveis `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET` ou `WHATSAPP_VERIFY_TOKEN`. As rotas respondem 404 nesse caso.
- `pyproject.toml` inclui o pacote `wabot*`.
- Commits com `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.

## Decisões desta fase (pesquisa em 07/10/2026)

- **Provedor:** Cloud API oficial da Meta, sem BSP. Bibliotecas não oficiais (Baileys, Evolution) descartadas pelo risco de banimento do número. O Telegram continua funcionando em paralelo.
- **Sem grupos no WhatsApp:** a Groups API exige Official Business Account e aceita no máximo 8 participantes. A família usa o modo privado (cada pessoa fala com o bot, todos no mesmo grupo financeiro).
- **Sem templates:** o bot só responde a mensagens do usuário (inclusive alertas de limite, que voltam junto da resposta), então tudo acontece dentro da janela de atendimento de 24h. Pela página oficial de preços, mensagens fora de template dentro da janela são gratuitas.
- **Convite:** `https://wa.me/<número>?text=join_<token>`. O link abre o WhatsApp com o texto preenchido; a pessoa só toca em enviar.
- **Vínculo com a conta web:** o mesmo código de 8 caracteres; no WhatsApp a pessoa envia `/start <código>`. O painel ganha um botão "Abrir no WhatsApp" quando `NEXT_PUBLIC_WHATSAPP_NUMBER` está configurado.
- **Só texto e botões:** áudio, imagem e outros tipos recebem uma resposta explicando que, por enquanto, só texto é entendido.
- **Reentregas:** a Meta reenvia webhooks; os ids de mensagem (`wamid`) já processados são descartados (memória, últimos 2048).
- **Mensagens longas:** texto acima de 4096 caracteres é dividido em várias mensagens.

---

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `backend/app/config.py` | Variáveis do WhatsApp e `whatsapp_enabled` |
| `backend/wabot/__init__.py` (novo) | Pacote |
| `backend/wabot/parse.py` (novo) | Assinatura e conversão do payload em eventos |
| `backend/wabot/client.py` (novo) | Montagem do payload e envio pela Graph API |
| `backend/wabot/dispatch.py` (novo) | Roteador de texto e processamento de eventos |
| `backend/wabot/webhook.py` (novo) | Rotas `GET`/`POST /whatsapp/webhook` |
| `backend/core/conversation.py` | `help_text(channel)` |
| `backend/app/main.py` | Inclui a rota do WhatsApp |
| `frontend/src/components/telegram-link-code.tsx` | Botão "Abrir no WhatsApp" |

---

### Task 1: Configuração, parse e assinatura

**Files:**
- Modify: `backend/app/config.py`, `backend/pyproject.toml`, `backend/.env.example`
- Create: `backend/wabot/__init__.py`, `backend/wabot/parse.py`
- Test: `backend/tests/test_whatsapp_parse.py`

**Interfaces:**
- Produces: `settings.whatsapp_*` e `settings.whatsapp_enabled`; `wabot.parse.verify_signature(raw: bytes, header: str | None, app_secret: str) -> bool`; `WhatsAppEvent(kind: str, message: IncomingMessage, wamid: str)` com `kind` em `"text" | "button" | "unsupported"`; `parse_webhook(payload: dict) -> list[WhatsAppEvent]`.

- [ ] **Step 1: Testes que falham**

`backend/tests/test_whatsapp_parse.py`:

```python
import hashlib
import hmac

from app.config import settings
from wabot.parse import parse_webhook, verify_signature

SECRET = "app-secret"


def _sign(raw: bytes) -> str:
    return "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()


def _payload(*messages, contacts=None, statuses=None):
    value = {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"}}
    if contacts is not None:
        value["contacts"] = contacts
    if messages:
        value["messages"] = list(messages)
    if statuses:
        value["statuses"] = statuses
    return {"object": "whatsapp_business_account", "entry": [{"id": "waba", "changes": [{"field": "messages", "value": value}]}]}


def test_signature_valid():
    raw = b'{"a":1}'
    assert verify_signature(raw, _sign(raw), SECRET)


def test_signature_rejects_tampered_body_missing_header_and_empty_secret():
    raw = b'{"a":1}'
    assert not verify_signature(b'{"a":2}', _sign(raw), SECRET)
    assert not verify_signature(raw, None, SECRET)
    assert not verify_signature(raw, "abc", SECRET)
    assert not verify_signature(raw, _sign(raw), "")


def test_parse_text_with_contact_name():
    events = parse_webhook(_payload(
        {"from": "5511999990000", "id": "wamid.1", "type": "text", "text": {"body": "gastei 50"}},
        contacts=[{"wa_id": "5511999990000", "profile": {"name": "Ana"}}],
    ))
    assert len(events) == 1
    e = events[0]
    assert (e.kind, e.wamid) == ("text", "wamid.1")
    m = e.message
    assert (m.channel, m.external_user_id, m.chat_id, m.display_name, m.text, m.chat_type, m.message_id) == (
        "whatsapp", "5511999990000", "5511999990000", "Ana", "gastei 50", "private", "wamid.1",
    )


def test_parse_button_reply_uses_button_id():
    events = parse_webhook(_payload(
        {"from": "551", "id": "wamid.2", "type": "interactive",
         "interactive": {"type": "button_reply", "button_reply": {"id": "approve:u1", "title": "Aprovar"}}},
    ))
    assert (events[0].kind, events[0].message.text) == ("button", "approve:u1")


def test_parse_unsupported_type():
    events = parse_webhook(_payload({"from": "551", "id": "wamid.3", "type": "audio", "audio": {"id": "x"}}))
    assert events[0].kind == "unsupported"


def test_statuses_and_garbage_are_ignored():
    assert parse_webhook(_payload(statuses=[{"id": "wamid.1", "status": "read"}])) == []
    assert parse_webhook({}) == []
    assert parse_webhook(_payload({"type": "text", "text": {"body": "sem remetente"}})) == []


def test_whatsapp_enabled_requires_all_settings(monkeypatch):
    for name in ("whatsapp_access_token", "whatsapp_phone_number_id", "whatsapp_app_secret", "whatsapp_verify_token"):
        monkeypatch.setattr(settings, name, "x")
    assert settings.whatsapp_enabled
    monkeypatch.setattr(settings, "whatsapp_app_secret", "")
    assert not settings.whatsapp_enabled
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/app/config.py`, novos campos depois de `cors_origins`:

```python
    # WhatsApp Cloud API. O canal fica desligado se faltar qualquer um dos quatro primeiros.
    whatsapp_access_token: str = ""
    whatsapp_phone_number_id: str = ""
    whatsapp_app_secret: str = ""
    whatsapp_verify_token: str = ""
    # Numero do bot so com digitos (DDI + DDD + numero), para links wa.me.
    whatsapp_number: str = ""
    whatsapp_graph_version: str = "v26.0"
```

e a propriedade:

```python
    @property
    def whatsapp_enabled(self) -> bool:
        return all((
            self.whatsapp_access_token,
            self.whatsapp_phone_number_id,
            self.whatsapp_app_secret,
            self.whatsapp_verify_token,
        ))
```

`backend/pyproject.toml`: `include = ["app*", "agent*", "tgbot*", "core*", "wabot*"]`.

`backend/.env.example`, no fim:

```
# WhatsApp Cloud API (opcional; o canal fica desligado se algum dos quatro primeiros faltar)
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=
WHATSAPP_VERIFY_TOKEN=
# Numero do bot so com digitos, ex.: 5511999990000
WHATSAPP_NUMBER=
WHATSAPP_GRAPH_VERSION=v26.0
```

`backend/wabot/__init__.py`: vazio.

`backend/wabot/parse.py`:

```python
"""Conversao do webhook da WhatsApp Cloud API em eventos do nucleo."""
import hashlib
import hmac
from dataclasses import dataclass

from core.messages import IncomingMessage

CHANNEL = "whatsapp"


def verify_signature(raw: bytes, header: str | None, app_secret: str) -> bool:
    """X-Hub-Signature-256: HMAC-SHA256 do corpo cru com o App Secret. Precisa
    ser o corpo exato recebido; JSON re-serializado nao bate."""
    if not app_secret or not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header[len("sha256="):], expected)


@dataclass(frozen=True)
class WhatsAppEvent:
    kind: str  # "text", "button" ou "unsupported"
    message: IncomingMessage
    wamid: str


def parse_webhook(payload: dict) -> list[WhatsAppEvent]:
    events: list[WhatsAppEvent] = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name", "") for c in value.get("contacts", [])}
            for raw in value.get("messages", []):
                sender, wamid = raw.get("from"), raw.get("id")
                if not sender or not wamid:
                    continue
                kind, text = _kind_and_text(raw)
                events.append(WhatsAppEvent(
                    kind=kind,
                    wamid=wamid,
                    message=IncomingMessage(
                        channel=CHANNEL,
                        external_user_id=sender,
                        display_name=names.get(sender, ""),
                        chat_id=sender,
                        text=text,
                        message_id=wamid,
                    ),
                ))
    return events


def _kind_and_text(raw: dict) -> tuple[str, str]:
    if raw.get("type") == "text":
        return "text", (raw.get("text") or {}).get("body", "")
    interactive = raw.get("interactive") or {}
    if raw.get("type") == "interactive" and interactive.get("type") == "button_reply":
        return "button", interactive["button_reply"].get("id", "")
    return "unsupported", ""
```

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `feat(whatsapp): configuracao, assinatura e parse do webhook`

---

### Task 2: Cliente de envio

**Files:**
- Create: `backend/wabot/client.py`
- Test: `backend/tests/test_whatsapp_client.py`

**Interfaces:**
- Produces: `build_payloads(out: OutgoingMessage) -> list[dict]`; `WhatsAppClient(token, phone_number_id, version, transport=None)` com `async send(outgoing: list[OutgoingMessage]) -> None` (erros da Graph API são logados, não levantados); `TEXT_LIMIT = 4096`, `BUTTON_BODY_LIMIT = 1024`, `BUTTON_TITLE_LIMIT = 20`, `MAX_BUTTONS = 3`.

- [ ] **Step 1: Testes que falham**

`backend/tests/test_whatsapp_client.py`:

```python
import json

import httpx
import pytest

from core.messages import Button, OutgoingMessage
from wabot.client import TEXT_LIMIT, WhatsAppClient, build_payloads


def test_text_payload():
    [p] = build_payloads(OutgoingMessage("5511", "Olá"))
    assert p == {
        "messaging_product": "whatsapp", "recipient_type": "individual", "to": "5511",
        "type": "text", "text": {"body": "Olá", "preview_url": False},
    }


def test_reply_context():
    [p] = build_payloads(OutgoingMessage("5511", "ok", reply_to="wamid.9"))
    assert p["context"] == {"message_id": "wamid.9"}


def test_long_text_is_split():
    payloads = build_payloads(OutgoingMessage("5511", "a" * (TEXT_LIMIT + 10)))
    assert [len(p["text"]["body"]) for p in payloads] == [TEXT_LIMIT, 10]


def test_buttons_payload_limits():
    buttons = tuple(Button(f"Aprovar pessoa número {i}", f"approve:{i}") for i in range(5))
    [p] = build_payloads(OutgoingMessage("5511", "Aprovar?", buttons=buttons))
    assert p["type"] == "interactive"
    action = p["interactive"]["action"]["buttons"]
    assert len(action) == 3
    assert action[0] == {"type": "reply", "reply": {"id": "approve:0", "title": "Aprovar pessoa númer"}}
    assert p["interactive"]["body"] == {"text": "Aprovar?"}


@pytest.mark.asyncio
async def test_send_posts_to_graph_with_token():
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    client = WhatsAppClient("tok", "123", "v26.0", transport=httpx.MockTransport(handler))
    await client.send([OutgoingMessage("5511", "um"), OutgoingMessage("5511", "dois")])

    assert [str(r.url) for r in seen] == ["https://graph.facebook.com/v26.0/123/messages"] * 2
    assert seen[0].headers["authorization"] == "Bearer tok"
    assert json.loads(seen[1].content)["text"]["body"] == "dois"


@pytest.mark.asyncio
async def test_send_logs_graph_errors_without_raising(caplog):
    client = WhatsAppClient("tok", "123", "v26.0", transport=httpx.MockTransport(
        lambda r: httpx.Response(400, json={"error": {"message": "fora da janela"}})
    ))
    await client.send([OutgoingMessage("5511", "oi")])
    assert "fora da janela" in caplog.text
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/wabot/client.py`:

```python
"""Envio de mensagens pela WhatsApp Cloud API (Graph API)."""
import logging

import httpx

from core.messages import OutgoingMessage

logger = logging.getLogger("bot")

GRAPH_URL = "https://graph.facebook.com"
TEXT_LIMIT = 4096
BUTTON_BODY_LIMIT = 1024
BUTTON_TITLE_LIMIT = 20
MAX_BUTTONS = 3


def _base(out: OutgoingMessage) -> dict:
    payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": out.chat_id}
    if out.reply_to:
        payload["context"] = {"message_id": out.reply_to}
    return payload


def build_payloads(out: OutgoingMessage) -> list[dict]:
    if out.buttons:
        buttons = [
            {"type": "reply", "reply": {"id": b.action[:256], "title": b.label[:BUTTON_TITLE_LIMIT]}}
            for b in out.buttons[:MAX_BUTTONS]
        ]
        return [{
            **_base(out),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": out.text[:BUTTON_BODY_LIMIT]},
                "action": {"buttons": buttons},
            },
        }]
    chunks = [out.text[i:i + TEXT_LIMIT] for i in range(0, len(out.text), TEXT_LIMIT)] or [""]
    return [{**_base(out), "type": "text", "text": {"body": chunk, "preview_url": False}} for chunk in chunks]


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, version: str, transport: httpx.AsyncBaseTransport | None = None):
        self._url = f"{GRAPH_URL}/{version}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {token}"}
        self._transport = transport

    async def send(self, outgoing: list[OutgoingMessage]) -> None:
        async with httpx.AsyncClient(headers=self._headers, transport=self._transport, timeout=30) as client:
            for out in outgoing:
                for payload in build_payloads(out):
                    response = await client.post(self._url, json=payload)
                    if response.status_code >= 400:
                        # Nao levanta: uma falha de envio nao deve derrubar as proximas mensagens.
                        logger.error(
                            "Falha ao enviar WhatsApp para %s: %s %s",
                            out.chat_id, response.status_code, response.text[:300],
                        )
```

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `feat(whatsapp): cliente de envio pela Graph API`

---

### Task 3: Roteador de texto e ajuda por canal

**Files:**
- Create: `backend/wabot/dispatch.py`
- Modify: `backend/core/conversation.py`
- Test: `backend/tests/test_whatsapp_dispatch.py`, `backend/tests/test_conversation.py`

**Interfaces:**
- Consumes: `process_message`, `process_start`, `help_message`, `invite_command` (núcleo), `process_button` (`core.group_chat`), `WhatsAppEvent` (Task 1).
- Produces: `core.conversation.help_text(channel: str) -> str` (`HELP_TEXT == help_text("telegram")`); `wabot.dispatch.invite_link(number: str) -> Callable[[str], str]`; `async route_text(msg, *, api_base_url, transport) -> list[OutgoingMessage]`; `async handle_event(event, *, client, api_base_url, transport) -> None`; `UNSUPPORTED_REPLY`.

- [ ] **Step 1: Testes que falham**

`tests/test_conversation.py`, acrescentar:

```python
def test_help_text_hides_telegram_group_commands_on_whatsapp():
    from core.conversation import HELP_TEXT, help_text

    assert HELP_TEXT == help_text("telegram")
    assert "/vincular" in help_text("telegram")
    whatsapp = help_text("whatsapp")
    assert "/vincular" not in whatsapp and "/f " not in whatsapp
    assert "/convidar" in whatsapp and "/ajuda" in whatsapp
```

`backend/tests/test_whatsapp_dispatch.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/core/conversation.py`: substituir a constante `HELP_TEXT` por:

```python
_HELP_COMMANDS = [
    "/start: iniciar ou reiniciar o assistente",
    "/convidar: gerar link de convite para um familiar",
]
# Grupos so existem no Telegram (no WhatsApp a Groups API exige conta oficial).
_TELEGRAM_GROUP_COMMANDS = [
    "/vincular: ligar um grupo do Telegram ao seu grupo financeiro (no grupo)",
    "/desvincular: desligar o grupo do Telegram (no grupo)",
    "/f <mensagem>: falar comigo dentro de um grupo do Telegram",
]
_HELP_FEATURES = [
    "- Registrar receitas e despesas ('Gastei R$ 150 no mercado')",
    "- Desfazer o último lançamento ('Desfaz o último')",
    "- Consultar saldo do mês ('Qual meu saldo?')",
    "- Ver extrato ('Mostre meus gastos de junho')",
    "- Resumo por categoria ('Quanto gastei com alimentação?')",
    "- Definir limites ('Limite de R$ 500 para Alimentação')",
    "- Ver limites ('Quais são meus limites?')",
]


def help_text(channel: str) -> str:
    commands = _HELP_COMMANDS + (_TELEGRAM_GROUP_COMMANDS if channel == "telegram" else [])
    commands.append("/ajuda: exibir esta mensagem")
    return (
        "Comandos disponíveis:\n\n" + "\n".join(commands)
        + "\n\nO que posso fazer por você:\n" + "\n".join(_HELP_FEATURES)
    )


HELP_TEXT = help_text("telegram")
```

e `help_message` passa a usar `help_text(msg.channel)`.

`backend/wabot/dispatch.py`:

```python
"""O WhatsApp nao tem comandos nativos: este roteador traduz o texto para as
funcoes do nucleo e envia as respostas."""
import re
from typing import Callable

from app.config import settings
from core.conversation import help_message, invite_command, process_message, process_start
from core.group_chat import process_button
from core.messages import IncomingMessage, OutgoingMessage

from .client import WhatsAppClient
from .parse import WhatsAppEvent

UNSUPPORTED_REPLY = "Por enquanto só entendo mensagens de texto. Escreva o que você precisa, por exemplo: 'gastei R$ 50 no mercado'."
_JOIN = re.compile(r"^join_[A-Za-z0-9-]+$")


def invite_link(number: str) -> Callable[[str], str]:
    # Abre o WhatsApp com "join_<token>" ja digitado; a pessoa so toca em enviar.
    return lambda token: f"https://wa.me/{number}?text=join_{token}"


async def route_text(msg: IncomingMessage, *, api_base_url: str, transport) -> list[OutgoingMessage]:
    text = msg.text.strip()
    if _JOIN.match(text):
        return process_start(msg, text)

    command, _, arg = text.partition(" ")
    command = command.lower().lstrip("/")
    if command == "start":
        return process_start(msg, arg.strip() or None)
    if command == "ajuda" and not arg:
        return help_message(msg)
    if command == "convidar" and not arg:
        return invite_command(msg, invite_link(settings.whatsapp_number))
    return await process_message(
        msg,
        api_base_url=api_base_url,
        transport=transport,
        invite_link=invite_link(settings.whatsapp_number),
    )


async def handle_event(event: WhatsAppEvent, *, client: WhatsAppClient, api_base_url: str, transport) -> None:
    if event.kind == "unsupported":
        outgoing = [OutgoingMessage(chat_id=event.message.chat_id, text=UNSUPPORTED_REPLY)]
    elif event.kind == "button":
        outgoing = process_button(event.message)
    else:
        outgoing = await route_text(event.message, api_base_url=api_base_url, transport=transport)
    await client.send(outgoing)
```

- [ ] **Step 4: Rodar a suíte.**
- [ ] **Step 5: Commit** `feat(whatsapp): roteador de texto e ajuda por canal`

---

### Task 4: Webhook

**Files:**
- Create: `backend/wabot/webhook.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_whatsapp_webhook.py`

**Interfaces:**
- Consumes: Tasks 1 a 3.
- Produces: `wabot.webhook.router` com `GET` e `POST /whatsapp/webhook`; `RecentIds(maxlen: int).seen(key: str) -> bool`; `make_client() -> WhatsAppClient`.

- [ ] **Step 1: Testes que falham**

`backend/tests/test_whatsapp_webhook.py`:

```python
import hashlib
import hmac
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.config import settings
from wabot import webhook
from wabot.webhook import RecentIds

SECRET = "app-secret"


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_access_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_phone_number_id", "123")
    monkeypatch.setattr(settings, "whatsapp_app_secret", SECRET)
    monkeypatch.setattr(settings, "whatsapp_verify_token", "verifica")
    monkeypatch.setattr(webhook, "_recent", RecentIds(100))


def _body(wamid="wamid.1", text="oi"):
    return json.dumps({"entry": [{"changes": [{"value": {
        "contacts": [{"wa_id": "5511", "profile": {"name": "Ana"}}],
        "messages": [{"from": "5511", "id": wamid, "type": "text", "text": {"body": text}}],
    }}]}]}).encode()


def _post(client, raw, signature=None):
    sig = signature or "sha256=" + hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return client.post("/whatsapp/webhook", content=raw, headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"})


def test_routes_are_404_when_disabled(client):
    assert client.get("/whatsapp/webhook").status_code == 404
    assert client.post("/whatsapp/webhook", content=b"{}").status_code == 404


def test_verification_echoes_challenge(client, enabled):
    r = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verifica", "hub.challenge": "1158201444"})
    assert r.status_code == 200
    assert r.text == "1158201444"


def test_verification_rejects_wrong_token(client, enabled):
    r = client.get("/whatsapp/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "1"})
    assert r.status_code == 403


def test_post_rejects_bad_signature(client, enabled):
    with patch.object(webhook, "handle_event", AsyncMock()) as handle:
        r = _post(client, _body(), signature="sha256=deadbeef")
    assert r.status_code == 403
    handle.assert_not_called()


def test_post_processes_event_once(client, enabled):
    with patch.object(webhook, "handle_event", AsyncMock()) as handle, patch.object(webhook, "make_client"):
        assert _post(client, _body()).status_code == 200
        assert _post(client, _body()).status_code == 200  # reentrega da Meta

    assert handle.await_count == 1
    event = handle.await_args.args[0]
    assert (event.message.text, event.message.display_name) == ("oi", "Ana")
    assert handle.await_args.kwargs["api_base_url"] == "http://internal"


def test_post_rejects_invalid_json(client, enabled):
    assert _post(client, b"nao-e-json").status_code == 400


def test_recent_ids_evicts_oldest():
    recent = RecentIds(2)
    assert not recent.seen("a")
    assert recent.seen("a")
    recent.seen("b")
    recent.seen("c")
    assert not recent.seen("a")
```

- [ ] **Step 2: Rodar e ver falhar.**

- [ ] **Step 3: Implementação**

`backend/wabot/webhook.py`:

```python
"""Webhook da WhatsApp Cloud API dentro da propria API."""
import hmac
import json
import logging
from collections import OrderedDict

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse

from app.config import settings

from .client import WhatsAppClient
from .dispatch import handle_event
from .parse import WhatsAppEvent, parse_webhook, verify_signature

logger = logging.getLogger("bot")

WEBHOOK_PATH = "/whatsapp/webhook"
# Host ficticio: com ASGITransport as tools chamam o app em processo.
INTERNAL_API_BASE_URL = "http://internal"

router = APIRouter(tags=["whatsapp"])


class RecentIds:
    """Ids ja processados (a Meta reentrega webhooks). Em memoria, um worker."""

    def __init__(self, maxlen: int):
        self._maxlen = maxlen
        self._ids: OrderedDict[str, None] = OrderedDict()

    def seen(self, key: str) -> bool:
        if key in self._ids:
            return True
        self._ids[key] = None
        if len(self._ids) > self._maxlen:
            self._ids.popitem(last=False)
        return False


_recent = RecentIds(2048)


def make_client() -> WhatsAppClient:
    return WhatsAppClient(
        settings.whatsapp_access_token,
        settings.whatsapp_phone_number_id,
        settings.whatsapp_graph_version,
    )


def _require_enabled() -> None:
    if not settings.whatsapp_enabled:
        raise HTTPException(status_code=404)


@router.get(WEBHOOK_PATH)
async def verify_webhook(request: Request):
    _require_enabled()
    params = request.query_params
    token = params.get("hub.verify_token", "")
    if params.get("hub.mode") == "subscribe" and hmac.compare_digest(token, settings.whatsapp_verify_token):
        return PlainTextResponse(params.get("hub.challenge", ""))
    raise HTTPException(status_code=403, detail="Token de verificação inválido.")


@router.post(WEBHOOK_PATH)
async def receive_webhook(request: Request, background: BackgroundTasks):
    _require_enabled()
    raw = await request.body()
    if not verify_signature(raw, request.headers.get("X-Hub-Signature-256"), settings.whatsapp_app_secret):
        raise HTTPException(status_code=403, detail="Assinatura inválida.")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise HTTPException(status_code=400, detail="JSON inválido.")

    events = [e for e in parse_webhook(payload) if not _recent.seen(e.wamid)]
    if events:
        # Responde 200 na hora; o LLM roda depois, sem a Meta estourar timeout e reenviar.
        background.add_task(_process, events, httpx.ASGITransport(app=request.app))
    return {"ok": True}


async def _process(events: list[WhatsAppEvent], transport: httpx.AsyncBaseTransport) -> None:
    client = make_client()
    for event in events:
        try:
            await handle_event(event, client=client, api_base_url=INTERNAL_API_BASE_URL, transport=transport)
        except Exception:
            logger.exception("Falha ao processar mensagem do WhatsApp %s", event.wamid)
```

`backend/app/main.py`: `from wabot.webhook import router as whatsapp_router` e `app.include_router(whatsapp_router)`.

- [ ] **Step 4: Rodar a suíte e um smoke test** com o app real (`uvicorn`) e uma Graph API falsa local: verificação do `hub.challenge`, POST assinado com `/start`, texto livre (agente simulado), `/convidar` e reentrega do mesmo `wamid`, conferindo os payloads recebidos pela Graph falsa. Para apontar o cliente para a Graph falsa no smoke test, substituir `wabot.client.GRAPH_URL`.
- [ ] **Step 5: Commit** `feat(whatsapp): webhook com verificacao, assinatura e processamento em background`

---

### Task 5: Painel e documentação

- [ ] `frontend/src/components/telegram-link-code.tsx`: com `NEXT_PUBLIC_WHATSAPP_NUMBER` definido, mostrar também o botão "Abrir no WhatsApp e vincular", com `href={`https://wa.me/${whatsappNumber}?text=${encodeURIComponent(`/start ${code}`)}`}`. O texto do card passa a falar em "Telegram ou WhatsApp". `frontend/.env.local.example` ganha `NEXT_PUBLIC_WHATSAPP_NUMBER=`. `npx tsc --noEmit` e `next build`.
- [ ] README: seção "WhatsApp" com o passo a passo da Meta (app do tipo Business, produto WhatsApp, número, token permanente de System User, URL do webhook `https://<api>/whatsapp/webhook`, verify token, assinatura do campo `messages`, App Secret), as variáveis, o que funciona (tudo do privado) e as limitações (sem grupos, só texto, janela de 24h irrelevante porque o bot só responde). `render.yaml` ganha as variáveis `WHATSAPP_*` com `sync: false`.
- [ ] PENDENTE: Fase 5 em "Concluido"; nova pendência "testar o fluxo no número real da Meta".
- [ ] Spec: Fase 5 aponta para este plano e registra as decisões.
- [ ] Commit `docs: fase 5 (WhatsApp)`.
