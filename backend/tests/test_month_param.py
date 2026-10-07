import pytest


@pytest.mark.parametrize("path", ["/transactions/", "/summary/"])
@pytest.mark.parametrize("month", ["2026-13", "2026-6", "junho", "2026-06-01", "26-06"])
def test_invalid_month_is_422(client, valid_token, path, month):
    response = client.get(path, params={"month": month}, headers={"Authorization": f"Bearer {valid_token}"})
    assert response.status_code == 422
