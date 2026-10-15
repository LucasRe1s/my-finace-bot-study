# -*- coding: utf-8 -*-
"""Deduplicacao de updates entre instancias (serverless nao tem memoria compartilhada).

Telegram e Meta reentregam o webhook quando a resposta demora ou falha. A chave
e gravada antes de processar: a primeira instancia que conseguir inserir
processa, as demais ignoram.
"""
from postgrest.exceptions import APIError

from app.database import get_service_supabase

UNIQUE_VIOLATION = "23505"


def claim_update(key: str) -> bool:
    """True se a chave e nova (deve processar); False se ja foi vista."""
    try:
        get_service_supabase().table("processed_updates").insert({"key": key}).execute()
    except APIError as exc:
        if exc.code == UNIQUE_VIOLATION:
            return False
        raise
    return True
