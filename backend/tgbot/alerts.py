# -*- coding: utf-8 -*-
from telegram import Bot


async def check_and_send_alerts(
    bot: Bot,
    telegram_id: int,
    category: str,
    spent: float,
    monthly_limit: float,
) -> None:
    """Envia alerta ao usuário se limite de categoria atingiu 80% ou 100%."""
    if monthly_limit <= 0:
        return

    percent = (spent / monthly_limit) * 100

    if percent >= 100:
        msg = (
            f"ALERTA: O limite mensal de {category} foi atingido.\n"
            f"Gasto: R$ {spent:,.2f} | Limite: R$ {monthly_limit:,.2f} (100%)"
        ).replace(",", "X").replace(".", ",").replace("X", ".")
        await bot.send_message(chat_id=telegram_id, text=msg)

    elif percent >= 80:
        msg = (
            f"Atenção: {percent:.0f}% do limite mensal de {category} foi utilizado.\n"
            f"Gasto: R$ {spent:,.2f} | Limite: R$ {monthly_limit:,.2f}"
        ).replace(",", "X").replace(".", ",").replace("X", ".")
        await bot.send_message(chat_id=telegram_id, text=msg)
