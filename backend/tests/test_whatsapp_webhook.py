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
