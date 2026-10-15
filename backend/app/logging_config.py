import logging


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx loga a URL de cada request em INFO, e a URL da Bot API contem o
    # token do bot (https://api.telegram.org/bot<TOKEN>/...). httpx2 e o fork
    # usado por anthropic e pelo cliente de teste do Starlette.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
