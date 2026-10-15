# Ponto de entrada da Vercel (Python serverless). Toda rota cai aqui via
# rewrite em vercel.json; o roteamento real e do FastAPI.
from app.main import app  # noqa: F401
