# -*- coding: utf-8 -*-
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from .handlers import handle_start, handle_help, handle_message
from app.config import settings


def build_app(api_base_url: str = "http://localhost:8000") -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    app.bot_data["api_base_url"] = api_base_url

    app.add_handler(CommandHandler("start", handle_start))
    app.add_handler(CommandHandler("ajuda", handle_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    return app


def main():
    import logging
    from dotenv import load_dotenv
    load_dotenv()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    app = build_app()
    logging.getLogger("bot").info("Bot @finncyBot iniciado. Aguardando mensagens...")
    app.run_polling(allowed_updates=["message"])


if __name__ == "__main__":
    main()
