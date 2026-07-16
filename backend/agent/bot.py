import os
from agno.agent import Agent
from agno.models.groq import Groq

from .prompts import SYSTEM_PROMPT


def create_agent(tools: list) -> Agent:
    return Agent(
        model=Groq(id="llama-3.3-70b-versatile", api_key=os.getenv("GROQ_API_KEY")),
        description="Assistente Financeiro formal para controle financeiro pessoal",
        instructions=[SYSTEM_PROMPT],
        tools=tools,
        markdown=False,
    )
