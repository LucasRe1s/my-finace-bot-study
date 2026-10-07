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
