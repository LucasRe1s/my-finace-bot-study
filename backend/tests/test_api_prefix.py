"""Vercel Services entrega o caminho original (/api/...) ao servico; o binding
interno do frontend chama sem o prefixo. O entrypoint aceita os dois."""
from fastapi.testclient import TestClient

from api.index import app


def test_public_path_with_api_prefix():
    client = TestClient(app)
    assert client.get("/api/health").json() == {"status": "ok"}


def test_internal_path_without_prefix():
    client = TestClient(app)
    assert client.get("/health").json() == {"status": "ok"}


def test_slash_redirect_stays_under_api_prefix():
    client = TestClient(app)
    response = client.get("/api/transactions", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"].endswith("/api/transactions/")


def test_prefix_only_matches_whole_segment():
    client = TestClient(app)
    assert client.get("/apidocs").status_code == 404
