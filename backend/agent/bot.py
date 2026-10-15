import os
from agno.agent import Agent
from agno.models.groq import Groq

from app.config import settings

from .prompts import SYSTEM_PROMPT


def create_agent(tools: list) -> Agent:
    return Agent(
        model=Groq(id=settings.groq_model, api_key=settings.groq_api_key or os.getenv("GROQ_API_KEY")),
        description="Assistente Financeiro formal para controle financeiro pessoal",
        instructions=[SYSTEM_PROMPT],
        tools=tools,
        markdown=False,
    )
