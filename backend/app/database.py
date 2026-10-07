from functools import lru_cache
from typing import Optional
from supabase import create_client, Client
from .config import settings


def get_supabase(token: Optional[str] = None) -> Client:
    """Cria o client Supabase. Se `token` for passado, repassa o JWT do usuário
    pro PostgREST para que as queries rodem como role `authenticated` (RLS
    avaliando o `auth.uid()` real) em vez de sempre como `anon`."""
    client = create_client(settings.supabase_url, settings.supabase_key)
    if token:
        client.postgrest.auth(token)
    return client


@lru_cache
def get_service_supabase() -> Client:
    """Client com a service_role key, que bypassa RLS. Usar so em operacoes do
    sistema sem usuario logado: bot achando usuario pelo telegram_id, historico
    de conversa, consumo de codigo de vinculo, preview e aceite de convite."""
    if not settings.supabase_service_role_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY nao configurada no backend.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
