from agno.agent import Agent
from agno.models.anthropic import Claude

from .prompts import SYSTEM_PROMPT


def create_agent(tools: list) -> Agent:
    """Cria instância do agente Agno com as tools fornecidas."""
    return Agent(
        model=Claude(id="claude-haiku-4-5-20251001"),
        description="Assistente Financeiro formal para controle financeiro pessoal",
        instructions=[SYSTEM_PROMPT],
        tools=tools,
        markdown=False,
    )
