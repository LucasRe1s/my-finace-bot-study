def test_health_no_auth(client):
    response = client.get("/health")
    assert response.status_code == 200


def test_protected_endpoint_without_token(client):
    response = client.get("/transactions/")
    assert response.status_code == 403


def test_protected_endpoint_invalid_token(client):
    response = client.get(
        "/transactions/",
        headers={"Authorization": "Bearer token_invalido"}
    )
    assert response.status_code == 401
