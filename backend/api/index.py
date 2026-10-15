# Ponto de entrada da Vercel (Python serverless). Toda rota cai aqui via
# rewrite em vercel.json; o roteamento real e do FastAPI.
import sys
from pathlib import Path

# A Vercel pode carregar este arquivo sem a raiz do backend no sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app  # noqa: E402,F401
