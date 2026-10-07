from core.alerts import limit_alert_message


def test_no_alert_below_80_percent():
    assert limit_alert_message("Lazer", 79.0, 100.0) is None


def test_attention_at_80_percent():
    msg = limit_alert_message("Alimentação", 850.0, 1000.0)
    assert msg.startswith("Atenção: 85% do limite mensal de Alimentação")
    assert "R$ 850,00" in msg and "R$ 1.000,00" in msg


def test_alert_at_100_percent():
    msg = limit_alert_message("Lazer", 1200.0, 1000.0)
    assert msg.startswith("ALERTA: O limite mensal de Lazer foi atingido.")


def test_zero_limit_never_alerts():
    assert limit_alert_message("Lazer", 10.0, 0) is None
