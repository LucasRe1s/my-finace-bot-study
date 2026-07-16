import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from agent.tools import build_tools, is_raw_provider_error, resolve_leaked_tool_call


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


def test_is_raw_provider_error_detects_groq_tool_use_failed():
    raw = (
        '{"error":{"message":"Failed to call a function. Please adjust your prompt.",'
        '"type":"invalid_request_error","code":"tool_use_failed","failed_generation":"..."}}'
    )
    assert is_raw_provider_error(raw) is True


def test_is_raw_provider_error_false_for_normal_reply():
    assert is_raw_provider_error("Confirmo o registro: despesa de R$ 50,00 em Alimentação.") is False


@pytest.mark.asyncio
async def test_criar_grupo_success():
    tools = build_tools("fake-token", "http://localhost:8000")
    criar_grupo = next(t for t in tools if t.__name__ == "criar_grupo")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"id": "group-uuid", "name": "Minha Família", "owner_id": "user-uuid"}

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await criar_grupo()

    assert "criado com sucesso" in result


@pytest.mark.asyncio
async def test_criar_grupo_error():
    tools = build_tools("fake-token", "http://localhost:8000")
    criar_grupo = next(t for t in tools if t.__name__ == "criar_grupo")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = '{"detail": "Erro ao criar grupo. Tente novamente."}'

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        result = await criar_grupo(name="Minha Família")

    assert "Erro ao criar grupo" in result


@pytest.mark.asyncio
async def test_resolve_leaked_tool_call_none_when_no_leak():
    tools = build_tools("fake-token", "http://localhost:8000")
    result = await resolve_leaked_tool_call("Confirmo o registro. Confirma? (Sim/Não)", tools)
    assert result is None


@pytest.mark.asyncio
async def test_resolve_leaked_tool_call_executes_tool():
    tools = build_tools("fake-token", "http://localhost:8000")

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {
        "id": "tx-uuid",
        "amount": 1180.0,
        "type": "income",
        "category": "Outros",
        "description": "crédito na conta",
        "date": "2026-07-16",
    }

    leaked = (
        'Desculpe pelo ocorrido. <function=registrar_transacao>'
        '{"type": "income", "amount": 1180.00, "category": "Outros", '
        '"date": "", "description": "crédito na conta"}</function>'
    )

    with patch("httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
        mock_client.return_value.__aenter__.return_value.get = AsyncMock(
            return_value=MagicMock(status_code=200, json=MagicMock(return_value=[]))
        )
        result = await resolve_leaked_tool_call(leaked, tools)

    assert "R$ 1.180,00" in result
    assert "Outros" in result


@pytest.mark.asyncio
async def test_resolve_leaked_tool_call_unknown_function_returns_fallback():
    tools = build_tools("fake-token", "http://localhost:8000")
    leaked = '<function=deletar_conta>{"confirm": true}</function>'
    result = await resolve_leaked_tool_call(leaked, tools)
    assert result == "Desculpe, não consegui processar sua solicitação. Poderia tentar novamente?"


@pytest.mark.asyncio
async def test_resolve_leaked_tool_call_malformed_json_returns_fallback():
    tools = build_tools("fake-token", "http://localhost:8000")
    leaked = '<function=registrar_transacao>{amount: 100 sem aspas}</function>'
    result = await resolve_leaked_tool_call(leaked, tools)
    assert result == "Desculpe, não consegui processar sua solicitação. Poderia tentar novamente?"
