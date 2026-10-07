def _preflight(client, origin):
    return client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )


def test_cors_allows_configured_origin(client):
    response = _preflight(client, "http://localhost:3000")
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_blocks_unknown_origin(client):
    response = _preflight(client, "https://site-malicioso.example")
    assert "access-control-allow-origin" not in response.headers
