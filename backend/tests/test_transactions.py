import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import *
from tests.fakes import FakeSupabase


def test_create_transaction_success(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    mock_db.table.return_value.insert.return_value.execute.return_value.data = [{
        "id": "tx-uuid-789",
        "user_id": "user-uuid-123",
        "group_id": "group-uuid-456",
        "amount": 50.0,
        "type": "expense",
        "category": "Alimentação",
        "description": "Mercado",
        "date": "2026-06-25",
        "created_at": "2026-06-25T12:00:00Z",
    }]

    with patch("app.routers.transactions.get_supabase", return_value=mock_db):
        response = client.post(
            "/transactions/",
            json={
                "amount": 50.0,
                "type": "expense",
                "category": "Alimentação",
                "description": "Mercado",
                "date": "2026-06-25",
            },
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 201
    assert response.json()["amount"] == 50.0
    assert response.json()["category"] == "Alimentação"


def test_create_transaction_invalid_category(client, valid_token):
    response = client.post(
        "/transactions/",
        json={"amount": 50.0, "type": "expense", "category": "Mercado"},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 422


def test_list_transactions_includes_author_name(client, valid_token):
    user_db = MagicMock()
    user_db.table.return_value.select.return_value.eq.return_value.limit.return_value.execute.return_value.data = [
        {"group_id": "group-uuid-456"}
    ]
    base = {"amount": 50.0, "type": "expense", "category": "Alimentação", "description": "Mercado",
            "date": "2026-06-25", "group_id": "group-uuid-456", "created_at": "2026-06-25T10:00:00"}
    user_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute.return_value.data = [
        {**base, "id": "t1", "user_id": "user-uuid-123"},
        {**base, "id": "t2", "user_id": None},
    ]
    service_db = FakeSupabase()
    service_db.tables["users"] = [{"id": "user-uuid-123", "name": "Ana"}]

    with (
        patch("app.routers.transactions.get_supabase", return_value=user_db),
        patch("app.routers.transactions.get_service_supabase", return_value=service_db),
    ):
        response = client.get("/transactions/", headers={"Authorization": f"Bearer {valid_token}"})

    assert response.status_code == 200
    assert [t["user_name"] for t in response.json()] == ["Ana", None]


def _tx(id, user_id, minutes_ago):
    created = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return {"id": id, "user_id": user_id, "group_id": "g1", "amount": 10.0, "type": "expense",
            "category": "Lazer", "description": "x", "date": "2026-10-07", "created_at": created}


def _undo(client, valid_token, db):
    with patch("app.routers.transactions.get_supabase", return_value=db):
        return client.post("/transactions/undo-last", headers={"Authorization": f"Bearer {valid_token}"})


def test_undo_last_deletes_most_recent_own_transaction(client, valid_token):
    db = FakeSupabase()
    db.tables["transactions"] = [_tx("old", "user-uuid-123", 5), _tx("new", "user-uuid-123", 1), _tx("other", "user-uuid-999", 0)]

    response = _undo(client, valid_token, db)

    assert response.status_code == 200
    assert response.json()["id"] == "new"
    assert [t["id"] for t in db.tables["transactions"]] == ["old", "other"]


def test_undo_last_ignores_transactions_older_than_10_minutes(client, valid_token):
    db = FakeSupabase()
    db.tables["transactions"] = [_tx("old", "user-uuid-123", 11)]

    response = _undo(client, valid_token, db)

    assert response.status_code == 404
    assert len(db.tables["transactions"]) == 1
