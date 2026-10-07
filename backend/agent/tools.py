# -*- coding: utf-8 -*-
import httpx
import inspect
import json
import re
from datetime import date as DateType

from core.alerts import limit_alert_message

_LEAKED_FUNCTION_CALL = re.compile(r"<function=(\w+)>(\{.*?\})</function>", re.DOTALL)

_FALLBACK_MESSAGE = "Desculpe, não consegui processar sua solicitação. Poderia tentar novamente?"


def _fmt_brl(value: float) -> str:
    """Formata float para R$ 1.234,56"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def resolve_leaked_tool_call(reply: str, tools: list) -> str | None:
    """Alguns modelos (ex.: Llama via Groq) as vezes emitem a chamada de tool no
    formato de texto nativo do Llama (`<function=nome>{...}</function>`) em vez de
    usar o mecanismo estruturado de tool_calls da API -- nesse caso a tool nunca e
    executada e o texto vazado vira a resposta do bot. Detecta esse padrao, executa
    a tool manualmente com os argumentos parseados e retorna o resultado real.
    Retorna None se a resposta nao contiver esse vazamento."""
    match = _LEAKED_FUNCTION_CALL.search(reply)
    if not match:
        return None

    name, raw_args = match.group(1), match.group(2)
    fn = next((t for t in tools if t.__name__ == name), None)
    if fn is None:
        return _FALLBACK_MESSAGE

    try:
        args = json.loads(raw_args)
    except json.JSONDecodeError:
        return _FALLBACK_MESSAGE

    valid_params = inspect.signature(fn).parameters
    kwargs = {k: v for k, v in args.items() if k in valid_params}
    return await fn(**kwargs)


def is_raw_provider_error(reply: str) -> bool:
    """Quando o modelo tenta uma chamada de tool malformada (ex.: sintaxe de
    function-call incompleta), a API as vezes rejeita a geracao e o agno
    devolve o JSON de erro bruto do provedor como se fosse a resposta final --
    em vez de levantar uma excecao. Detecta esse caso pra nao expor o erro cru
    ao usuario."""
    stripped = reply.strip()
    return stripped.startswith('{"error"') or "tool_use_failed" in stripped or "invalid_request_error" in stripped


def build_tools(
    user_token: str,
    api_base_url: str = "http://localhost:8000",
    transport: httpx.AsyncBaseTransport | None = None,
    alert_sink: list[str] | None = None,
) -> list:
    headers = {"Authorization": f"Bearer {user_token}"}

    def _client() -> httpx.AsyncClient:
        # Com transport (bot dentro da API), as chamadas vao direto para o app
        # FastAPI em processo, sem rede; sem ele, vao por HTTP para api_base_url.
        return httpx.AsyncClient(base_url=api_base_url, transport=transport, timeout=30)

    async def registrar_transacao(
        amount: float,
        type: str,
        category: str,
        description: str = "",
        date: str = None,
    ) -> str:
        """Registra uma transação financeira após confirmação do usuário.

        Args:
            amount: Valor em reais (positivo)
            type: Tipo da transação -- "income" para receita, "expense" para despesa
            category: Categoria (Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Vestuário, Outros)
            description: Descrição breve da transação
            date: Data no formato YYYY-MM-DD (padrão: hoje)
        """
        payload = {
            "amount": amount,
            "type": type,
            "category": category,
            "description": description,
            "date": date or str(DateType.today()),
        }
        async with _client() as client:
            response = await client.post(
                "/transactions/",
                json=payload,
                headers=headers,
            )
            if response.status_code == 201 and alert_sink is not None:
                limits_response = await client.get("/limits/", headers=headers)
                if limits_response.status_code == 200:
                    for lim in limits_response.json():
                        if lim["category"] == category:
                            alert = limit_alert_message(category, lim["spent"], lim["monthly_limit"])
                            if alert:
                                alert_sink.append(alert)
        if response.status_code == 201:
            tx = response.json()
            tipo = "Receita" if type == "income" else "Despesa"
            return f"Transação registrada com sucesso. {tipo} de {_fmt_brl(amount)} em {category} na data {tx['date']}."
        return f"Erro ao registrar transação: {response.text}"

    async def criar_grupo(name: str = "Minha Família") -> str:
        """Cria o grupo financeiro do usuário, caso ele ainda não tenha um.

        Args:
            name: Nome do grupo (padrão: "Minha Família")
        """
        async with _client() as client:
            response = await client.post(
                "/groups/",
                json={"name": name},
                headers=headers,
            )
        if response.status_code == 201:
            return f"Grupo '{name}' criado com sucesso. Você já pode registrar transações e definir limites."
        return f"Erro ao criar grupo: {response.text}"

    async def consultar_extrato(
        month: str = None,
        category: str = None,
        type: str = None,
    ) -> str:
        """Consulta o extrato de transações com filtros opcionais.

        Args:
            month: Mês no formato YYYY-MM (padrão: mês atual)
            category: Filtrar por categoria específica
            type: Filtrar por tipo -- "income" ou "expense"
        """
        params = {}
        if month:
            params["month"] = month
        if category:
            params["category"] = category
        if type:
            params["type"] = type

        async with _client() as client:
            response = await client.get(
                "/transactions/",
                params=params,
                headers=headers,
            )
        if response.status_code != 200:
            return f"Erro ao consultar extrato: {response.text}"

        transactions = response.json()
        if not transactions:
            return "Nenhuma transação encontrada para os filtros informados."

        lines = [f"Extrato -- {len(transactions)} transação(ões):"]
        for t in transactions[:20]:
            tipo = "+" if t["type"] == "income" else "-"
            autor = f" | {t['user_name']}" if t.get("user_name") else ""
            lines.append(f"  {tipo} {_fmt_brl(t['amount'])} | {t['category']} | {t['description']} | {t['date']}{autor}")
        if len(transactions) > 20:
            lines.append(f"  ... e mais {len(transactions) - 20} transação(ões).")
        return "\n".join(lines)

    async def desfazer_ultima_transacao() -> str:
        """Desfaz (apaga) a última transação registrada pelo próprio usuário nos últimos 10 minutos.
        Use somente depois que o usuário confirmar."""
        async with _client() as client:
            response = await client.post("/transactions/undo-last", headers=headers)
        if response.status_code == 200:
            tx = response.json()
            tipo = "Receita" if tx["type"] == "income" else "Despesa"
            descricao = tx.get("description") or "sem descrição"
            return f"Transação desfeita: {tipo} de {_fmt_brl(tx['amount'])} em {tx['category']} ({descricao})."
        if response.status_code == 404:
            return "Não há transação sua registrada nos últimos 10 minutos para desfazer."
        return f"Erro ao desfazer transação: {response.text}"

    async def consultar_resumo(month: str = None) -> str:
        """Consulta o resumo financeiro do mês com saldo e gastos por categoria.

        Args:
            month: Mês no formato YYYY-MM (padrão: mês atual)
        """
        params = {}
        if month:
            params["month"] = month

        async with _client() as client:
            response = await client.get(
                "/summary/",
                params=params,
                headers=headers,
            )
        if response.status_code != 200:
            return f"Erro ao consultar resumo: {response.text}"

        data = response.json()
        lines = [
            f"Resumo financeiro -- {data['month']}:",
            f"  Receitas: {_fmt_brl(data['total_income'])}",
            f"  Despesas: {_fmt_brl(data['total_expense'])}",
            f"  Saldo:    {_fmt_brl(data['balance'])}",
            "",
            "Gastos por categoria:",
        ]
        for item in data["by_category"]:
            lines.append(f"  {item['category']}: {_fmt_brl(item['total'])}")
        return "\n".join(lines)

    async def consultar_limites() -> str:
        """Consulta os limites mensais configurados por categoria e o percentual utilizado."""
        async with _client() as client:
            response = await client.get("/limits/", headers=headers)
        if response.status_code != 200:
            return f"Erro ao consultar limites: {response.text}"

        limits = response.json()
        if not limits:
            return "Nenhum limite configurado. Envie uma mensagem como 'Defina limite de R$ 500 para Alimentação'."

        lines = ["Limites mensais por categoria:"]
        for lim in limits:
            status = "EXCEDIDO" if lim["percent_used"] >= 100 else ("ATENÇÃO" if lim["percent_used"] >= 80 else "OK")
            lines.append(
                f"  {lim['category']}: {_fmt_brl(lim['spent'])} / {_fmt_brl(lim['monthly_limit'])} "
                f"({lim['percent_used']}%) [{status}]"
            )
        return "\n".join(lines)

    async def definir_limite(category: str, monthly_limit: float) -> str:
        """Define ou atualiza o limite mensal de gastos para uma categoria.

        Args:
            category: Categoria (Alimentação, Transporte, Moradia, Saúde, Educação, Lazer, Vestuário, Outros)
            monthly_limit: Valor limite mensal em reais
        """
        async with _client() as client:
            response = await client.post(
                "/limits/",
                json={"category": category, "monthly_limit": monthly_limit},
                headers=headers,
            )
        if response.status_code in (200, 201):
            return f"Limite de {_fmt_brl(monthly_limit)} definido para {category}."
        return f"Erro ao definir limite: {response.text}"

    return [
        registrar_transacao,
        criar_grupo,
        consultar_extrato,
        desfazer_ultima_transacao,
        consultar_resumo,
        consultar_limites,
        definir_limite,
    ]
