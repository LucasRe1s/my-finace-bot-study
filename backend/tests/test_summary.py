import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app
from tests.conftest import *


def test_get_summary_current_month(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"type": "income", "amount": 5000.0, "category": "Outros"},
        {"type": "expense", "amount": 150.0, "category": "Alimentação"},
        {"type": "expense", "amount": 50.0, "category": "Transporte"},
    ]

    with patch("app.routers.summary.get_supabase", return_value=mock_db):
        with patch("app.routers.summary._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/summary/?month=2026-06",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["month"] == "2026-06"
    assert data["total_income"] == 5000.0
    assert data["total_expense"] == 200.0
    assert data["balance"] == 4800.0
    assert len(data["by_category"]) == 2


def test_get_summary_by_category_sorted_desc(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"type": "expense", "amount": 50.0, "category": "Transporte"},
        {"type": "expense", "amount": 150.0, "category": "Alimentação"},
        {"type": "income", "amount": 3000.0, "category": "Outros"},
    ]

    with patch("app.routers.summary.get_supabase", return_value=mock_db):
        with patch("app.routers.summary._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/summary/?month=2026-06",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    by_cat = data["by_category"]
    assert by_cat[0]["category"] == "Alimentação"
    assert by_cat[0]["total"] == 150.0
    assert by_cat[1]["category"] == "Transporte"
    assert by_cat[1]["total"] == 50.0


def test_get_summary_no_month_defaults_to_current(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = []

    with patch("app.routers.summary.get_supabase", return_value=mock_db):
        with patch("app.routers.summary._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/summary/",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert "month" in data
    assert data["total_income"] == 0.0
    assert data["total_expense"] == 0.0
    assert data["balance"] == 0.0
    assert data["by_category"] == []


def test_get_summary_rounding(client, valid_token):
    mock_db = MagicMock()
    mock_db.table.return_value.select.return_value.eq.return_value.gte.return_value.lte.return_value.execute.return_value.data = [
        {"type": "income", "amount": 1000.005, "category": "Outros"},
        {"type": "expense", "amount": 33.333, "category": "Alimentação"},
        {"type": "expense", "amount": 66.667, "category": "Transporte"},
    ]

    with patch("app.routers.summary.get_supabase", return_value=mock_db):
        with patch("app.routers.summary._get_user_group", return_value="group-uuid-456"):
            response = client.get(
                "/summary/?month=2026-06",
                headers={"Authorization": f"Bearer {valid_token}"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["total_income"] == round(1000.005, 2)
    assert data["total_expense"] == round(33.333 + 66.667, 2)


def test_get_summary_requires_auth(client):
    response = client.get("/summary/?month=2026-06")
    assert response.status_code == 403
