"""Testes de redirecionamento de /conta/trades (recurso removido)."""
from __future__ import annotations

from urllib.parse import parse_qs, urlsplit
import pytest

from lodout.public_site import db
from lodout.public_site.server import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "_DB_PATH", tmp_path / "public_site.db")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _login(client, monkeypatch, steamid="76561198000000000"):
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: steamid)
    monkeypatch.setattr(
        "lodout.public_site.account.fetch_public_profile",
        lambda sid: {"name": "Fulano", "avatar_url": None})
    login_resp = client.get("/login")
    openid_params = parse_qs(urlsplit(login_resp.headers["Location"]).query)
    return_to = openid_params["openid.return_to"][0]
    query = {
        key: values[0]
        for key, values in parse_qs(urlsplit(return_to).query).items()
    }
    query.update({"openid.mode": "id_res", "openid.return_to": return_to})
    client.get("/login/callback", query_string=query)


def test_trades_sem_login_redireciona(client):
    resp = client.get("/conta/trades")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_trades_logado_redireciona_para_conta(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta/trades")
    assert resp.status_code == 302
    assert "/conta" in resp.headers["Location"]


def test_trades_extra_logado_redireciona_para_conta(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta/trades/0/remover")
    assert resp.status_code == 302
    assert "/conta" in resp.headers["Location"]


def test_link_trades_nao_aparece_no_dashboard_nem_subnav(client, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "/conta/trades" not in pagina
