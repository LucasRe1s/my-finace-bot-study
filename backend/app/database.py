from supabase import create_client, Client
from .config import settings


def get_supabase() -> Client:
    return create_client(settings.supabase_url, settings.supabase_key)
