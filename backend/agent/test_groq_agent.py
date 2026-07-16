"""
Agente de teste local usando Agno + Groq.
Roda sem backend/Supabase — simula as tools localmente.

Uso:
    cd backend
    python -m agent.test_groq_agent
"""

import os
from agno.agent import Agent
from agno.models.groq import Groq
from agno.tools import tool

from .prompts import SYSTEM_PROMPT


@tool
def registrar_transacao(
    amount: float,
    type: str,
    category: str,
    description: str,
    date: str,
) -> dict:
    """Registra uma transação financeira."""
    print(f"\n[TOOL] registrar_transacao chamada: {type} R$ {amount:.2f} em {category} — {description} ({date})")
    return {
        "id": "test-uuid-001",
        "amount": amount,
        "type": type,
        "category": category,
        "description": description,
        "date": date,
        "limit_alert": None,
    }


@tool
def consultar_resumo(month: str = "") -> dict:
    """Retorna resumo financeiro do mês."""
    print(f"\n[TOOL] consultar_resumo chamada: month={month or 'atual'}")
    return {
        "month": month or "2026-06",
        "total_income": 5000.00,
        "total_expense": 2340.50,
        "balance": 2659.50,
        "by_category": [
            {"category": "Alimentação", "total": 850.00},
            {"category": "Transporte", "total": 430.50},
            {"category": "Moradia", "total": 1060.00},
        ],
    }


@tool
def consultar_limites() -> list:
    """Retorna limites por categoria."""
    print("\n[TOOL] consultar_limites chamada")
    return [
        {"category": "Alimentação", "monthly_limit": 1000.00, "spent": 850.00, "percent_used": 85.0},
        {"category": "Transporte", "monthly_limit": 500.00, "spent": 430.50, "percent_used": 86.1},
    ]


def create_test_agent(model_id: str = "llama-3.3-70b-versatile") -> Agent:
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise EnvironmentError("GROQ_API_KEY nao definida. Adicione ao backend/.env")

    return Agent(
        model=Groq(id=model_id, api_key=api_key),
        description="Assistente Financeiro de teste local",
        instructions=[SYSTEM_PROMPT],
        tools=[registrar_transacao, consultar_resumo, consultar_limites],
        markdown=False,
    )


def main():
    from dotenv import load_dotenv
    load_dotenv()

    agent = create_test_agent()
    print("Agente Financeiro (Groq/Llama-3.3-70B) — digite 'sair' para encerrar\n")

    while True:
        user_input = input("Você: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("sair", "exit", "quit"):
            break

        response = agent.run(user_input)
        print(f"\nAgente: {response.content}\n")


if __name__ == "__main__":
    main()
