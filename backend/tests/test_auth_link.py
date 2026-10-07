from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_create_telegram_link_code(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        response = client.post(
            "/auth/telegram-link-code",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    body = response.json()
    assert len(body["code"]) == 8
    assert "expires_at" in body
    mock_db.table.assert_any_call("telegram_link_codes")


def test_public_telegram_link_endpoint_was_removed(client):
    response = client.post(
        "/auth/telegram-link",
        json={"code": "ABC12345", "telegram_id": 999888777},
    )
    assert response.status_code == 404


def test_link_code_generation_is_rate_limited(client, valid_token, monkeypatch):
    from app.routers import auth_link
    from core.rate_limit import SlidingWindowLimiter

    monkeypatch.setattr(auth_link, "_code_limiter", SlidingWindowLimiter(max_events=2, window_seconds=600))
    mock_db = MagicMock()
    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        codes = [client.post("/auth/telegram-link-code", headers={"Authorization": f"Bearer {valid_token}"}).status_code for _ in range(3)]
    assert codes == [201, 201, 429]
