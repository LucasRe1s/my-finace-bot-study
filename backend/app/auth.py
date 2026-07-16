import logging
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
from jwt import PyJWKClient

from .config import settings

logger = logging.getLogger("api")

# Tokens emitidos pelo Supabase Auth deste projeto sao assinados com uma chave
# assimetrica (ES256), verificada via JWKS. Ja os tokens que o bot Telegram gera
# para seus proprios usuarios (que nao tem sessao Supabase) usam HS256 com o
# secret compartilhado -- ver tgbot/handlers.py::_generate_user_token.
_jwks_client = PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json")


class BearerAuth(HTTPBearer):
    async def __call__(self, request: Request) -> Optional[HTTPAuthorizationCredentials]:
        credentials = await super().__call__(request)
        return credentials


security = BearerAuth(auto_error=False)


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Não autenticado",
        )
    token = credentials.credentials
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                audience="authenticated",
            )
        else:
            signing_key = _jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[header.get("alg", "ES256")],
                audience="authenticated",
            )
        return {"id": payload["sub"], "email": payload.get("email", ""), "token": token}
    except jwt.PyJWTError as e:
        logger.warning("JWT rejeitado: %s", e)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )
