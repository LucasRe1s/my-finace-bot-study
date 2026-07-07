import pytest
from unittest.mock import patch, MagicMock
from tests.conftest import *


def test_create_limit(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{
        "id": "limit-uuid",
        "group_id": "group-uuid-456",
        "category": "Alimentação",
        "monthly_limit": 500.0,
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = []

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        with patch("app.routers.limits._get_user_group", return_value="group-uuid-456"):
            response = client.post(
                "/limits/",
                json={"category": "Alimentação", "monthly_limit": 500.0},
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["monthly_limit"] == 500.0
    assert data["spent"] == 0.0
    assert data["percent_used"] == 0.0


def test_create_limit_with_existing_spend(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{
        "id": "limit-uuid",
        "group_id": "group-uuid-456",
        "category": "Alimentação",
        "monthly_limit": 500.0,
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"amount": 100.0},
        {"amount": 150.0},
    ]

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        with patch("app.routers.limits._get_user_group", return_value="group-uuid-456"):
            response = client.post(
                "/limits/",
                json={"category": "Alimentação", "monthly_limit": 500.0},
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["spent"] == 250.0
    assert data["percent_used"] == 50.0


def test_create_limit_invalid_category(client, valid_token):
    response = client.post(
        "/limits/",
        json={"category": "Supermercado", "monthly_limit": 500.0},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 422


def test_create_limit_zero_limit(client, valid_token):
    response = client.post(
        "/limits/",
        json={"category": "Alimentação", "monthly_limit": 0.0},
        headers={"Authorization": f"Bearer {valid_token}"},
    )
    assert response.status_code == 422


def test_create_limit_requires_auth(client):
    response = client.post(
        "/limits/",
        json={"category": "Alimentação", "monthly_limit": 500.0},
    )
    assert response.status_code == 403


def test_list_limits(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [
        {
            "id": "limit-uuid-1",
            "group_id": "group-uuid-456",
            "category": "Alimentação",
            "monthly_limit": 500.0,
        },
        {
            "id": "limit-uuid-2",
            "group_id": "group-uuid-456",
            "category": "Transporte",
            "monthly_limit": 200.0,
        },
    ]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = []

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        with patch("app.routers.limits._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/limits/",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["category"] == "Alimentação"
    assert data[0]["monthly_limit"] == 500.0
    assert data[0]["spent"] == 0.0
    assert data[0]["percent_used"] == 0.0
    assert data[1]["category"] == "Transporte"


def test_list_limits_empty(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.data = []

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        with patch("app.routers.limits._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/limits/",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    assert response.json() == []


def test_list_limits_requires_auth(client):
    response = client.get("/limits/")
    assert response.status_code == 403


def test_percent_used_over_100(client, valid_token):
    """Percentual pode ultrapassar 100% quando gasto excede o limite."""
    mock_db = MagicMock()
    mock_db.table.return_value.upsert.return_value.execute.return_value.data = [{
        "id": "limit-uuid",
        "group_id": "group-uuid-456",
        "category": "Alimentação",
        "monthly_limit": 100.0,
    }]
    mock_db.table.return_value.select.return_value.eq.return_value.eq.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"amount": 150.0},
    ]

    with patch("app.routers.limits.get_supabase", return_value=mock_db):
        with patch("app.routers.limits._get_user_group", return_value="group-uuid-456"):
            response = client.post(
                "/limits/",
                json={"category": "Alimentação", "monthly_limit": 100.0},
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 201
    data = response.json()
    assert data["spent"] == 150.0
    assert data["percent_used"] == 150.0
