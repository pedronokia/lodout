"""Testes das rotas de histórico pessoal -- Flask test client.

Mesmo padrão de `test_account_routes.py`. O ponto de histórico é
gravado por `account.py:conta()` -- essa rota precisa de um preço no
cache pra `evaluate_portfolio` fechar um `totals.market` numérico.
"""
from __future__ import annotations

import pytest
from urllib.parse import parse_qs, urlsplit

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


def test_listar_sem_login_redireciona(client):
    resp = client.get("/conta/historico")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_listar_sem_pontos_mostra_empty_state(client, monkeypatch):
    _login(client, monkeypatch)
    resp = client.get("/conta/historico")
    assert resp.status_code == 200
    assert "Nenhum item vendido".encode("utf-8") in resp.data
    assert "Evolução do valor do inventário".encode("utf-8") not in resp.data


def test_visitar_conta_grava_ponto_de_historico(client, monkeypatch):
    _login(client, monkeypatch)
    client.get("/conta")  # portfolio vazio -> totals.market == 0.0
    from lodout.public_site import user_history
    pontos = user_history.load_history("76561198000000000")
    assert len(pontos) == 1
    assert pontos[0]["total"] == 0.0


def test_visitar_conta_duas_vezes_sem_mudar_nao_duplica(client, monkeypatch):
    _login(client, monkeypatch)
    client.get("/conta")
    client.get("/conta")
    client.get("/conta")
    from lodout.public_site import user_history
    pontos = user_history.load_history("76561198000000000")
    assert len(pontos) == 1


def test_historico_mostra_item_vendido_e_lucro(client, monkeypatch):
    _login(client, monkeypatch)
    from lodout.public_site import user_vendidos
    user_vendidos.adicionar(
        "76561198000000000",
        name="AK-47 | Redline (Field-Tested)",
        custo=50.0,
        preco_venda=100.0,
        quantidade=1,
    )
    pagina = client.get("/conta/historico").data.decode("utf-8")
    assert "Nenhum item vendido" not in pagina
    assert "AK-47 | Redline" in pagina
    assert "R$ 50,00" in pagina
    assert "R$ 100,00" in pagina
    assert "Evolução do valor do inventário" not in pagina


def test_historico_mostra_hora_de_brasilia_nao_utc(client, monkeypatch):
    # Data da venda formatada no fuso de Brasília.
    _login(client, monkeypatch)
    from lodout.public_site import user_vendidos
    import datetime
    ts_utc = datetime.datetime(
        2024, 1, 2, 2, 30, tzinfo=datetime.timezone.utc).timestamp()
    user_vendidos.adicionar(
        "76561198000000000",
        name="AK-47 | Redline (Field-Tested)",
        custo=50.0,
        preco_venda=100.0,
        quantidade=1,
    )
    # Ajusta o sell_ts para o instante UTC de teste
    vendas = user_vendidos.load("76561198000000000")
    vendas[0]["sell_ts"] = ts_utc
    from lodout.public_site import user_store
    user_store.save_user_json("76561198000000000", "vendidos", vendas)

    pagina = client.get("/conta/historico").data.decode("utf-8")
    # 02/01/2024 02:30 UTC == 01/01/2024 23:30 em Brasília (UTC-3)
    assert "01/01/2024" in pagina
    assert "02/01/2024" not in pagina


def test_historico_isolado_entre_contas(client, monkeypatch):
    _login(client, monkeypatch, steamid="111")
    from lodout.public_site import user_vendidos
    user_vendidos.adicionar(
        "111",
        name="AWP | Asiimov (Field-Tested)",
        custo=200.0,
        preco_venda=300.0,
        quantidade=1,
    )
    pagina_111 = client.get("/conta/historico").data.decode("utf-8")
    assert "AWP | Asiimov" in pagina_111

    client.get("/logout")
    _login(client, monkeypatch, steamid="222")
    pagina_222 = client.get("/conta/historico").data.decode("utf-8")
    assert "AWP | Asiimov" not in pagina_222
    assert "Nenhum item vendido" in pagina_222
