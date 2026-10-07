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
