def _brl(value: float) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def limit_alert_message(category: str, spent: float, monthly_limit: float) -> str | None:
    """Texto do alerta quando o gasto da categoria atinge 80% ou 100% do limite."""
    if monthly_limit <= 0:
        return None
    percent = (spent / monthly_limit) * 100
    if percent >= 100:
        return (
            f"ALERTA: O limite mensal de {category} foi atingido.\n"
            f"Gasto: {_brl(spent)} | Limite: {_brl(monthly_limit)} (100%)"
        )
    if percent >= 80:
        return (
            f"Atenção: {percent:.0f}% do limite mensal de {category} foi utilizado.\n"
            f"Gasto: {_brl(spent)} | Limite: {_brl(monthly_limit)}"
        )
    return None
