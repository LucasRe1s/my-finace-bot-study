# -*- coding: utf-8 -*-
from groq import AsyncGroq

from app.config import settings

WHISPER_MODEL = "whisper-large-v3-turbo"


async def transcribe_audio(audio: bytes, filename: str = "voice.ogg") -> str:
    """Transcreve um áudio (ogg/opus do Telegram, mp3, m4a...) usando Whisper via Groq."""
    client = AsyncGroq(api_key=settings.groq_api_key)
    result = await client.audio.transcriptions.create(
        file=(filename, audio),
        model=WHISPER_MODEL,
        language="pt",
    )
    return result.text.strip()
