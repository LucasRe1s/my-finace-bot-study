import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import *


def test_create_transaction_success(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.limit.return_value.single.return_value.execute.return_value.data = {
        "group_id": "group-uuid-456"
    }
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


def test_list_transactions(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.routers.transactions.get_supabase", return_value=mock_db):
        response = client.get(
            "/transactions/",
            headers={"Authorization": f"Bearer {valid_token}"},
        )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
