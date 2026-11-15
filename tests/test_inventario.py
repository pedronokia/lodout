"""Inventário da Steam na conta (plans/archive/conta-inventario.md, fase 2).
Sem rede: `steam_api.fetch_inventory` é sempre substituído."""
from __future__ import annotations

import pytest

from lodout import steam_api
from lodout.public_site import inventario, user_portfolio, user_store, worker

SID = "76561198000000001"


def _inv(*nomes, qtd=1):
    return [{"name": n, "quantity": qtd, "icon": f"h-{n}"} for n in nomes]


# ── mesclar ──────────────────────────────────────────────────────────

def test_mesclar_novo_entra_sem_preco_pago():
    pos, resumo = inventario.mesclar([], _inv("AK-47 | Redline (Field-Tested)"), agora=1.0)
    assert pos == [{"name": "AK-47 | Redline (Field-Tested)", "cost": None,
                    "quantity": 1, "added_ts": 1.0, "source": "steam",
                    "icon": "h-AK-47 | Redline (Field-Tested)"}]
    assert resumo == {"novos": 1, "atualizados": 0, "removidos": 0}


def test_mesclar_atualiza_quantidade_e_mantem_preco_pago():
    antes = [{"name": "Caixa X", "cost": 2.5, "quantity": 1, "source": "steam"}]
    pos, resumo = inventario.mesclar(antes, _inv("Caixa X", qtd=3))
    assert pos[0]["cost"] == 2.5 and pos[0]["quantity"] == 3
    assert resumo["atualizados"] == 1


def test_mesclar_item_vendido_sai_junto_com_o_preco_pago():
    # Decisão do usuário (2026-11-15): "se vendeu, apaga os dados".
    antes = [{"name": "Vendido", "cost": 100.0, "quantity": 1, "source": "steam"},
             {"name": "Fica", "cost": 5.0, "quantity": 1, "source": "steam"}]
    pos, resumo = inventario.mesclar(antes, _inv("Fica"))
    assert [p["name"] for p in pos] == ["Fica"]
    assert resumo["removidos"] == 1


def test_mesclar_item_a_mao():
    antes = [
        {"name": "Fora do inventário", "cost": 1.0, "quantity": 1, "source": "manual"},
        {"name": "No inventário", "cost": 9.0, "quantity": 1, "source": "manual"},
        {"name": "Duas linhas", "cost": 1.0, "quantity": 1, "source": "manual"},
        {"name": "Duas linhas", "cost": 2.0, "quantity": 1, "source": "manual"},
    ]
    pos, resumo = inventario.mesclar(antes, _inv("No inventário", "Duas linhas"))
    por_nome = {}
    for p in pos:
        por_nome.setdefault(p["name"], []).append(p)
    # Adicionado à mão e fora do inventário: fica como está.
    assert por_nome["Fora do inventário"][0]["source"] == "manual"
    # Uma linha à mão que aparece no inventário: passa a ser acompanhada
    # por ele, com o preço pago mantido.
    assert por_nome["No inventário"][0]["source"] == "steam"
    assert por_nome["No inventário"][0]["cost"] == 9.0
    # Várias linhas à mão do mesmo item: a pessoa controla, nada muda.
    assert [p["cost"] for p in por_nome["Duas linhas"]] == [1.0, 2.0]
    assert resumo["novos"] == 0


# ── sincronizar ──────────────────────────────────────────────────────

def test_sincronizar_grava_posicoes_e_estado(monkeypatch):
    monkeypatch.setattr(steam_api, "fetch_inventory",
                        lambda sid: (steam_api.INV_OK, _inv("Caixa X")))
    est = inventario.sincronizar(SID)
    assert est["status"] == "ok" and est["resumo"]["novos"] == 1
    assert [p["name"] for p in user_portfolio.load_positions(SID)] == ["Caixa X"]
    assert inventario.estado(SID)["status"] == "ok"


def test_sincronizar_inventario_privado_nao_mexe_na_conta(monkeypatch):
    sid = "76561198000000002"
    user_portfolio.add_position(sid, "Meu item", 10.0)
    monkeypatch.setattr(steam_api, "fetch_inventory",
                        lambda sid: (steam_api.INV_PRIVATE, []))
    est = inventario.sincronizar(sid)
    assert est["status"] == "private"
    assert [p["name"] for p in user_portfolio.load_positions(sid)] == ["Meu item"]


def test_sincronizar_pendentes_so_contas_ativas_e_para_no_bloqueio(monkeypatch):
    monkeypatch.setattr(steam_api, "RATE_LIMIT_DELAY_S", 0.0)
    monkeypatch.setattr(user_store, "usuarios_ativos",
                        lambda desde: ["a", "b", "c"])
    # "a" já foi sincronizada há pouco.
    user_store.save_user_json("a", "inventario_sync", {"ts": 9e18})
    chamadas = []

    def fake(sid):
        chamadas.append(sid)
        return (steam_api.INV_RATE_LIMITED, []) if sid == "b" else (steam_api.INV_OK, [])

    monkeypatch.setattr(steam_api, "fetch_inventory", fake)
    assert inventario.sincronizar_pendentes(ate_ts=9e18) == 1
    assert chamadas == ["b"]


def test_usuarios_ativos_filtra_pelo_ultimo_login():
    user_store.upsert_user("recente")
    assert "recente" in user_store.usuarios_ativos(0)
    assert user_store.usuarios_ativos(9e18) == []


# ── site e worker ────────────────────────────────────────────────────

@pytest.fixture
def client():
    from lodout.public_site.server import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _logado(client, sid=SID):
    with client.session_transaction() as s:
        s["steamid"] = sid


def test_login_dispara_a_sincronizacao(client, monkeypatch):
    disparos = []
    monkeypatch.setattr(inventario, "sincronizar_em_segundo_plano",
                        lambda sid: disparos.append(sid))
    monkeypatch.setattr(
        "lodout.public_site.account.steam_openid.verify_callback",
        lambda args: SID)
    monkeypatch.setattr(
        "lodout.public_site.account.fetch_public_profile",
        lambda sid: {"name": "Fulano", "avatar_url": None})
    from urllib.parse import parse_qs, urlsplit
    login = client.get("/login")
    volta = parse_qs(urlsplit(login.headers["Location"]).query)["openid.return_to"][0]
    query = {k: v[0] for k, v in parse_qs(urlsplit(volta).query).items()}
    query.update({"openid.mode": "id_res", "openid.return_to": volta})
    client.get("/login/callback", query_string=query)
    assert disparos == [SID]


def test_abrir_a_conta_nunca_consulta_a_steam(client, monkeypatch):
    def proibido(sid):
        raise AssertionError("abrir /conta não pode consultar a Steam")
    monkeypatch.setattr(steam_api, "fetch_inventory", proibido)
    _logado(client)
    assert client.get("/conta").status_code == 200


def test_conta_explica_inventario_privado(client):
    user_store.save_user_json(SID, "inventario_sync", {"status": "private", "ts": 1.0})
    user_portfolio.add_position(SID, "Meu item", 10.0)
    _logado(client)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Seu inventário da Steam está privado" in pagina
    assert "steamcommunity.com/my/edit/settings" in pagina


def test_conta_pede_preco_pago_dos_itens_novos(client):
    user_store.save_user_json(SID, "inventario_sync", {
        "status": "ok", "ts": 1.0, "resumo": {"novos": 2}})
    user_portfolio.add_position(SID, "Meu item", 10.0)
    _logado(client)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "2 itens novos: informe quanto pagou" in pagina


def test_worker_sincroniza_inventarios_so_com_a_chave_ligada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(inventario, "sincronizar_pendentes",
                        lambda ate_ts, deve_parar: chamadas.append(ate_ts))
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    worker._esperar(3600)
    assert chamadas == []
    monkeypatch.setenv("LODOUT_INVENTARIO_DIARIO", "1")
    worker._esperar(3600)
    assert len(chamadas) == 1


def test_buscando_inventario_nao_fica_preso(client):
    import time
    sid = "76561198000000003"
    user_store.save_user_json(sid, "inventario_sync", {
        "em_andamento": True, "iniciado_ts": time.time() - 3600,
        "status": "ok", "ts": time.time() - 7200})
    user_portfolio.add_position(sid, "Meu item", 10.0)
    _logado(client, sid)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Buscando seu inventário" not in pagina
    assert "Inventário da Steam atualizado" in pagina


# ── lotes: o mesmo item pago por valores diferentes (2026-11-15) ─────

def test_separar_e_juntar_lotes():
    sid = "76561198000000010"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa X", "cost": 2.0, "quantity": 5, "source": "steam"}])
    novo = user_portfolio.separar(sid, "Caixa X", 2)
    assert novo
    pos = user_portfolio.load_positions(sid)
    assert [(p["quantity"], p["cost"]) for p in pos] == [(3, 2.0), (2, None)]
    assert all(p.get("lote") for p in pos)
    # Fora de 1..unidades-1 não separa.
    assert user_portfolio.separar(sid, "Caixa X", 3, lote=pos[0]["lote"]) is None
    # Valor só do lote novo.
    user_portfolio.update_position_cost(sid, "Caixa X", 5.0, lote=novo)
    pos = user_portfolio.load_positions(sid)
    assert [p["cost"] for p in pos] == [2.0, 5.0]
    # Juntar: valor médio ponderado (3x2 + 2x5) / 5 = 3,20.
    assert user_portfolio.juntar(sid, "Caixa X") == "ok"
    pos = user_portfolio.load_positions(sid)
    assert len(pos) == 1 and pos[0]["quantity"] == 5 and pos[0]["cost"] == 3.2


def test_juntar_recusa_lote_com_e_sem_valor():
    sid = "76561198000000011"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa X", "cost": 2.0, "quantity": 1, "source": "steam", "lote": "a"},
        {"name": "Caixa X", "cost": None, "quantity": 1, "source": "steam", "lote": "b"}])
    assert user_portfolio.juntar(sid, "Caixa X") == "misto"
    assert len(user_portfolio.load_positions(sid)) == 2


def test_mesclar_respeita_lotes():
    lotes = [
        {"name": "Caixa X", "cost": 2.0, "quantity": 3, "source": "steam", "lote": "a", "added_ts": 1},
        {"name": "Caixa X", "cost": 5.0, "quantity": 2, "source": "steam", "lote": "b", "added_ts": 2},
    ]
    # Igual: nada muda.
    pos, _ = inventario.mesclar(lotes, _inv("Caixa X", qtd=5))
    assert [(p["lote"], p["quantity"]) for p in pos] == [("a", 3), ("b", 2)]
    # Chegaram 2: lote novo sem valor, pra pessoa informar.
    pos, _ = inventario.mesclar(lotes, _inv("Caixa X", qtd=7))
    assert [(p["quantity"], p["cost"]) for p in pos] == [(3, 2.0), (2, 5.0), (2, None)]
    # Vendeu 4: saem primeiro as mais antigas (3 do lote a, 1 do b).
    pos, _ = inventario.mesclar(lotes, _inv("Caixa X", qtd=1))
    assert [(p["lote"], p["quantity"]) for p in pos] == [("b", 1)]
    # Lote sem valor sai antes dos com valor.
    com_sem = lotes + [{"name": "Caixa X", "cost": None, "quantity": 1,
                        "source": "steam", "lote": "c", "added_ts": 3}]
    pos, _ = inventario.mesclar(com_sem, _inv("Caixa X", qtd=5))
    assert [p["lote"] for p in pos] == ["a", "b"]
    # Vendeu tudo: todos os lotes saem.
    pos, resumo = inventario.mesclar(lotes, [])
    assert pos == [] and resumo["removidos"] == 2


def test_conta_separa_e_salva_valor_por_lote(client):
    from lodout.public_site import catalogo
    sid = "76561198000000012"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa L", "cost": 2.0, "quantity": 4, "source": "steam"}])
    _logado(client, sid)
    import re
    pagina = client.get("/conta").data.decode("utf-8")
    token = re.search(r'name="csrf_token" value="([^"]+)"', pagina).group(1)
    assert "valores diferentes?" in pagina
    r = client.post("/conta/posicoes/Caixa L/separar",
                    data={"quantidade": "1", "csrf_token": token})
    assert r.status_code == 302
    pagina = client.get("/conta").data.decode("utf-8")
    assert "lote 1 de 2" in pagina and "lote 2 de 2" in pagina
    assert "Separado: 1 unidade ficou numa linha própria" in pagina
    assert 'class="status status-sucesso"' in pagina
    lote2 = user_portfolio.load_positions(sid)[1]["lote"]
    r = client.post("/conta/posicoes/Caixa L/custo",
                    data={"cost": "7,00", "lote": lote2, "csrf_token": token},
                    headers={"Accept": "application/json"})
    assert r.get_json()["ok"] is True
    assert [p["cost"] for p in user_portfolio.load_positions(sid)] == [2.0, 7.0]
    client.post("/conta/posicoes/Caixa L/remover", data={"lote": lote2, "csrf_token": token})
    assert [p["quantity"] for p in user_portfolio.load_positions(sid)] == [3]
