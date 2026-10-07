from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_create_group(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "group-uuid-456",
        "name": "Família Silva",
        "owner_id": "user-uuid-123",
    }]

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.post(
            "/groups/",
            json={"name": "Família Silva"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["name"] == "Família Silva"
    mock_db.table.assert_any_call("users")
    mock_db.table.return_value.upsert.assert_called_once()


def test_send_invite(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "invite-uuid",
        "group_id": "group-uuid-456",
        "email": "familiar@example.com",
        "token": "abc-token-123",
    }]

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.post(
            "/groups/invite",
            json={"email": "familiar@example.com"},
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["email"] == "familiar@example.com"


def test_list_members(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {"user_id": "user-uuid-123", "role": "owner"},
        {"user_id": "user-uuid-456", "role": "member"},
    ]

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.get(
            "/groups/members",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["role"] == "owner"


def test_list_members_no_group(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = []

    with patch("app.routers.groups.get_supabase", return_value=mock_db):
        response = client.get(
            "/groups/members",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    assert response.json() == []


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
