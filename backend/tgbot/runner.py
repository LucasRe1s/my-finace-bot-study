# -*- coding: utf-8 -*-
import httpx
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .handlers import handle_start, handle_help, handle_invite, handle_message
from app.config import settings


def build_app(
    api_base_url: str,
    api_transport: httpx.AsyncBaseTransport | None = None,
    webhook: bool = False,
) -> Application:
    # concurrent_updates: uma resposta lenta do LLM nao trava os outros usuarios.
    builder = Application.builder().token(settings.telegram_bot_token).concurrent_updates(8)
    if webhook:
        # Em webhook os updates chegam pela rota do FastAPI (tgbot/webhook.py),
        # nao ha polling.
        builder = builder.updater(None)
    app = builder.build()

    app.bot_data["api_base_url"] = api_base_url
    app.bot_data["api_transport"] = api_transport

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ajuda", handle_help))
    app.add_handler(CommandHandler("convidar", handle_invite))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main():
    """Modo polling, so para desenvolvimento local. Use um bot de dev separado:
    o polling apaga o webhook registrado no bot de producao."""
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = build_app(api_base_url=settings.api_base_url)
    logging.getLogger("bot").info("Bot iniciado em modo polling. API em %s", settings.api_base_url)
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
