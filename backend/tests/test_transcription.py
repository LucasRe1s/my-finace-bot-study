import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_transcribe_audio_sends_bytes_to_groq_whisper():
    from agent.transcription import transcribe_audio

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create = AsyncMock(return_value=MagicMock(text="  Gastei 50 reais no mercado  "))

    with patch("agent.transcription.AsyncGroq", return_value=mock_client):
        text = await transcribe_audio(b"fake-ogg", filename="voice.ogg")

    assert text == "Gastei 50 reais no mercado"
    kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert kwargs["file"] == ("voice.ogg", b"fake-ogg")
    assert kwargs["model"] == "whisper-large-v3-turbo"
    assert kwargs["language"] == "pt"
