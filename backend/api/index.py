# Ponto de entrada na Vercel (Services: "entrypoint": "api.index:app").
import sys
from pathlib import Path

# A Vercel pode carregar este arquivo sem a raiz do backend no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app as fastapi_app  # noqa: E402

PREFIX = "/api"


async def app(scope, receive, send):
    """O rewrite publico /api/(.*) entrega o caminho original ao servico; o
    binding interno do frontend chama sem prefixo. Quando vier com /api, ele
    vira root_path (pela spec ASGI o path continua completo): o roteamento
    ignora o prefixo e redirects/URLs absolutas continuam sob /api."""
    if scope["type"] in ("http", "websocket"):
        path = scope.get("path", "")
        if path == PREFIX or path.startswith(PREFIX + "/"):
            scope = {**scope, "root_path": PREFIX}
    await fastapi_app(scope, receive, send)
