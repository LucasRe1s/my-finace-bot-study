import logging

from app.logging_config import configure_logging


def test_http_client_loggers_do_not_log_urls_with_bot_token():
    """httpx loga a URL de cada request em INFO; a URL do Telegram contem o token."""
    configure_logging()
    for name in ("httpx", "httpx2", "httpcore"):
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING
    assert logging.getLogger("bot").getEffectiveLevel() == logging.INFO
