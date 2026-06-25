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


def test_send_invite(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }
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
