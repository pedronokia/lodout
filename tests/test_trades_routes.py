"""Testes das rotas de trades pessoais -- Flask test client.

Mesmo padrão de `test_account_routes.py`: `db._DB_PATH` monkeypatchado
(as rotas não recebem `path=` do chamador).
"""
from __future__ import annotations

import re
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


def _csrf_token(client):
    html = client.get("/conta/trades").data.decode("utf-8")
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return m.group(1)


def _troca(client, token, deu=(("AK-47 | Redline (Field-Tested)", "1", "50,00"),),
           recebeu=(("AWP | Asiimov (Field-Tested)", "1", "60,00"),), **extra):
    data = {"csrf_token": token, "deu_nome": [], "deu_qtd": [], "deu_valor": [],
            "recebeu_nome": [], "recebeu_qtd": [], "recebeu_valor": []}
    for lado, itens in (("deu", deu), ("recebeu", recebeu)):
        for nome, qtd, valor in itens:
            data[f"{lado}_nome"].append(nome)
            data[f"{lado}_qtd"].append(qtd)
            data[f"{lado}_valor"].append(valor)
    data.update(extra)
    return client.post("/conta/trades", data=data)


def test_listar_sem_login_redireciona(client):
    resp = client.get("/conta/trades")
    assert resp.status_code == 302


def test_pagina_explica_que_sao_trocas(client, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "Nenhuma troca registrada ainda" in pagina
    assert "Você deu" in pagina and "Você recebeu" in pagina
    assert "Itens vendidos" in pagina and "não paga a taxa da Steam" in pagina


def test_registrar_troca_mostra_os_dois_lados_e_o_saldo(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    resp = _troca(client, token,
                  deu=(("AK-47 | Redline (Field-Tested)", "2", "25,00"), ("", "1", "")),
                  recebeu=(("AWP | Asiimov (Field-Tested)", "1", "R$ 60,00"),),
                  notas="com o João", data="2026-11-10")
    assert resp.status_code == 302
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "Troca registrada: você recebeu R$ 10,00 a mais em valor" in pagina
    assert "10/11/2026" in pagina and "com o João" in pagina
    assert "AK-47 | Redline (Testada em Campo)" in pagina and "×2" in pagina
    assert "+R$ 10,00" in pagina


def test_troca_invalida_nao_grava(client, monkeypatch):
    from lodout.public_site import user_trocas
    _login(client, monkeypatch)
    token = _csrf_token(client)
    for kwargs in (
        {"recebeu": ()},                                             # um lado vazio
        {"deu": (("AK-47", "0", "10"),)},                            # quantidade 0
        {"deu": (("AK-47", "1", "abc"),)},                           # valor inválido
        {"deu": (("AK-47", "1", "0"),)},                             # valor zero
        {"data": "2999-01-01"},                                      # data no futuro
    ):
        r = _troca(client, token, **kwargs)
        assert r.status_code == 302
    assert user_trocas.load("76561198000000000") == []
    assert "Nada foi registrado" in client.get("/conta/trades").data.decode("utf-8")


def test_troca_sem_csrf_falha(client, monkeypatch):
    _login(client, monkeypatch)
    _csrf_token(client)
    resp = _troca(client, "errado")
    assert resp.status_code in (400, 403)


def test_apagar_troca(client, monkeypatch):
    _login(client, monkeypatch)
    token = _csrf_token(client)
    _troca(client, token)
    client.post("/conta/trades/0/remover", data={"csrf_token": token})
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "A troca saiu da sua lista" in pagina
    assert "Nenhuma troca registrada ainda" in pagina


def test_trocas_isoladas_entre_contas(client, monkeypatch):
    _login(client, monkeypatch, steamid="76561198000000001")
    _troca(client, _csrf_token(client))
    _login(client, monkeypatch, steamid="76561198000000002")
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "Nenhuma troca registrada ainda" in pagina


def test_compra_e_venda_antigas_vao_para_itens_vendidos(client, monkeypatch):
    """17/11: "Meus trades" registrava compra e venda; isso agora vive em
    "Itens vendidos". Os registros antigos mudam de lugar na 1ª visita."""
    from lodout import trades as trades_mod
    from lodout.public_site import user_store, user_vendidos
    sid = "76561198000000003"
    user_store.save_user_json(sid, "trades", [
        trades_mod.build_trade("Caixa Z", 10.0, 15.0, 2)])
    _login(client, monkeypatch, steamid=sid)
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "1 registro de compra e venda que estava aqui foi para “Itens vendidos”" in pagina
    vendas = user_vendidos.load(sid)
    assert len(vendas) == 1 and vendas[0]["source"] == "trades" and vendas[0]["quantity"] == 2
    assert user_store.load_user_json(sid, "trades", None) == []
    hist = client.get("/conta/historico").data.decode("utf-8")
    assert "Caixa Z" in hist and ">apagar</button>" in hist and "desfazer venda" not in hist
    # Apagar uma venda vinda dos trades não põe nada na conta.
    token = re.search(r'name="csrf_token" value="([^"]+)"', hist).group(1)
    client.post("/conta/historico/vendidos/0/desfazer", data={"csrf_token": token})
    from lodout.public_site import user_portfolio
    assert user_vendidos.load(sid) == [] and user_portfolio.load_positions(sid) == []


def test_link_trades_aparece_no_dashboard_logado(client, monkeypatch):
    _login(client, monkeypatch)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "/conta/trades" in pagina


def test_troca_mostra_imagem_do_catalogo_e_saldo_de_hoje(client, monkeypatch):
    from lodout.public_site import catalogo
    monkeypatch.setattr(catalogo, "CAMBIO_FIXO", 1.0)
    conn = catalogo.conectar()
    catalogo.gravar(conn, "Rifles", [
        {"hash_name": "Caixa Z", "price": 1.0, "listings": 5, "name_color": "4b69ff", "icon": "hash-z"},
        {"hash_name": "Caixa Y", "price": 3.0, "listings": 5, "name_color": "4b69ff", "icon": "hash-y"}])
    conn.close()
    _login(client, monkeypatch)
    token = _csrf_token(client)
    _troca(client, token, deu=(("Caixa Z", "1", "2,00"),), recebeu=(("Caixa Y", "1", "2,50"),))
    pagina = client.get("/conta/trades").data.decode("utf-8")
    assert "hash-z" in pagina and "hash-y" in pagina
    assert "Hoje: <strong" in pagina and 'id="dialogo-remover"' in pagina
