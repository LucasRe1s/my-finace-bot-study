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
