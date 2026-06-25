# -*- coding: utf-8 -*-
import httpx
from datetime import date as DateType


def _fmt_brl(value: float) -> str:
    """Formata float para R$ 1.234,56"""
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_tools(
    user_token: str,
    api_base_url: str = "http://localhost:8000",
    bot=None,
    telegram_id=None,
) -> list:
    headers = {"Authorization": f"Bearer {user_token}"}

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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_base_url}/transactions/",
                json=payload,
                headers=headers,
            )
            if response.status_code == 201 and bot and telegram_id:
                limits_response = await client.get(f"{api_base_url}/limits/", headers=headers)
                if limits_response.status_code == 200:
                    for lim in limits_response.json():
                        if lim["category"] == category:
                            from tgbot.alerts import check_and_send_alerts
                            await check_and_send_alerts(
                                bot=bot,
                                telegram_id=telegram_id,
                                category=category,
                                spent=lim["spent"],
                                monthly_limit=lim["monthly_limit"],
                            )
        if response.status_code == 201:
            tx = response.json()
            tipo = "Receita" if type == "income" else "Despesa"
            return f"Transação registrada com sucesso. {tipo} de {_fmt_brl(amount)} em {category} na data {tx['date']}."
        return f"Erro ao registrar transação: {response.text}"

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

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_url}/transactions/",
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
            lines.append(f"  {tipo} {_fmt_brl(t['amount'])} | {t['category']} | {t['description']} | {t['date']}")
        if len(transactions) > 20:
            lines.append(f"  ... e mais {len(transactions) - 20} transação(ões).")
        return "\n".join(lines)

    async def consultar_resumo(month: str = None) -> str:
        """Consulta o resumo financeiro do mês com saldo e gastos por categoria.

        Args:
            month: Mês no formato YYYY-MM (padrão: mês atual)
        """
        params = {}
        if month:
            params["month"] = month

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_base_url}/summary/",
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
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{api_base_url}/limits/", headers=headers)
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
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{api_base_url}/limits/",
                json={"category": category, "monthly_limit": monthly_limit},
                headers=headers,
            )
        if response.status_code in (200, 201):
            return f"Limite de {_fmt_brl(monthly_limit)} definido para {category}."
        return f"Erro ao definir limite: {response.text}"

    return [
        registrar_transacao,
        consultar_extrato,
        consultar_resumo,
        consultar_limites,
        definir_limite,
    ]
