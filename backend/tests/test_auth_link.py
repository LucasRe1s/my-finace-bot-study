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


def test_consume_telegram_link_code_success(client):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = [
        {"code": "ABC12345", "user_id": "web-user-uuid", "used_at": None}
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = None

    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        response = client.post(
            "/auth/telegram-link",
            json={"code": "ABC12345", "telegram_id": 999888777},
        )

    assert response.status_code == 200
    assert response.json()["message"] == "Telegram vinculado com sucesso."
    mock_db.table.return_value.delete.assert_not_called()


def test_consume_telegram_link_code_invalid_or_expired(client):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = []

    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        response = client.post(
            "/auth/telegram-link",
            json={"code": "BADCODE1", "telegram_id": 999888777},
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Código inválido ou expirado."


def test_consume_telegram_link_code_merges_existing_bot_user(client):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.is_.return_value.gte.return_value.execute.return_value.data = [
        {"code": "ABC12345", "user_id": "web-user-uuid", "used_at": None}
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
        "id": "bot-only-user-uuid"
    }

    with patch("app.routers.auth_link.get_supabase", return_value=mock_db):
        response = client.post(
            "/auth/telegram-link",
            json={"code": "ABC12345", "telegram_id": 999888777},
        )

    assert response.status_code == 200
    update_calls = mock_db.table.return_value.update.call_args_list
    assert any(call.args[0].get("user_id") == "web-user-uuid" for call in update_calls)
    mock_db.table.return_value.delete.assert_called_once()
