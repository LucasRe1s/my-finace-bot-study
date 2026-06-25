import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from agent.tools import build_tools


@pytest.mark.asyncio
async def test_registrar_transacao_success():
    tools = build_tools("fake-token", "http://localhost:8000")
    registrar = next(t for t in tools if t.__name__ == "registrar_transacao")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "tx-uuid",
        "amount": 50.0,
        "type": "expense",
        "category": "Alimentação",
        "description": "Mercado",
        "date": "2026-06-25",
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await registrar(
            amount=50.0,
            type="expense",
            category="Alimentação",
            description="Mercado",
            date="2026-06-25",
        )

    assert "R$ 50,00" in result
    assert "Alimentação" in result


@pytest.mark.asyncio
async def test_consultar_resumo_success():
    tools = build_tools("fake-token", "http://localhost:8000")
    consultar = next(t for t in tools if t.__name__ == "consultar_resumo")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "month": "2026-06",
        "total_income": 5000.0,
        "total_expense": 800.0,
        "balance": 4200.0,
        "by_category": [{"category": "Alimentação", "total": 300.0}],
    }

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
        result = await consultar(month="2026-06")

    assert "R$ 4.200,00" in result
    assert "Alimentação" in result
