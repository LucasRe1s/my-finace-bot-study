import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI

from app.config import settings

SECRET = "segredo-de-teste"


@pytest.fixture
def webhook_secret(monkeypatch):
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)


@pytest.fixture
def fake_ptb():
    ptb = MagicMock()
    ptb.update_queue = asyncio.Queue()
    return ptb


def test_webhook_rejects_wrong_secret(client, webhook_secret, fake_ptb):
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": "errado"},
    )
    assert response.status_code == 403
    assert fake_ptb.update_queue.qsize() == 0


def test_webhook_rejects_when_secret_not_configured(client, monkeypatch, fake_ptb):
    monkeypatch.setattr(settings, "telegram_webhook_secret", "")
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": ""},
    )
    assert response.status_code == 403


def test_webhook_returns_503_when_bot_not_running(client, webhook_secret):
    client.app.state.telegram_app = None
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 1},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 503


def test_webhook_enqueues_update(client, webhook_secret, fake_ptb):
    client.app.state.telegram_app = fake_ptb
    response = client.post(
        "/telegram/webhook",
        json={"update_id": 42},
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert response.status_code == 200
    assert fake_ptb.update_queue.get_nowait().update_id == 42


@pytest.mark.asyncio
async def test_lifespan_off_does_not_start_bot(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "off")
    api = FastAPI()
    with patch("tgbot.webhook.build_app") as build_app:
        async with telegram_lifespan(api):
            assert api.state.telegram_app is None
    build_app.assert_not_called()


@pytest.mark.asyncio
async def test_lifespan_webhook_registers_and_stops(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "webhook")
    monkeypatch.setattr(settings, "public_base_url", "https://api.example.com/")
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)

    ptb = MagicMock()
    ptb.initialize = AsyncMock()
    ptb.start = AsyncMock()
    ptb.stop = AsyncMock()
    ptb.shutdown = AsyncMock()
    ptb.bot.set_webhook = AsyncMock()

    api = FastAPI()
    with patch("tgbot.webhook.build_app", return_value=ptb) as build_app:
        async with telegram_lifespan(api):
            assert api.state.telegram_app is ptb

    assert build_app.call_args.kwargs["webhook"] is True
    assert build_app.call_args.kwargs["api_transport"] is not None
    ptb.bot.set_webhook.assert_awaited_once_with(
        url="https://api.example.com/telegram/webhook",
        secret_token=SECRET,
        allowed_updates=["message"],
    )
    ptb.stop.assert_awaited_once()
    ptb.shutdown.assert_awaited_once()


@pytest.mark.asyncio
async def test_lifespan_webhook_requires_url_and_secret(monkeypatch):
    from tgbot.webhook import telegram_lifespan

    monkeypatch.setattr(settings, "telegram_mode", "webhook")
    monkeypatch.setattr(settings, "public_base_url", "")
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)

    with pytest.raises(RuntimeError, match="PUBLIC_BASE_URL"):
        async with telegram_lifespan(FastAPI()):
            pass


def test_build_app_webhook_has_no_updater():
    from tgbot.runner import build_app

    ptb = build_app(api_base_url="http://internal", webhook=True)
    assert ptb.updater is None
    assert ptb.bot_data["api_base_url"] == "http://internal"
