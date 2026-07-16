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
