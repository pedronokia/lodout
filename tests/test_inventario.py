"""Inventário da Steam na conta (plans/archive/conta-inventario.md, fase 2).
Sem rede: `steam_api.fetch_inventory` é sempre substituído."""
from __future__ import annotations

from pathlib import Path

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
    assert resumo == {"novos": 1, "atualizados": 0, "removidos": 0, "fora": 0}


def test_mesclar_atualiza_quantidade_e_mantem_preco_pago():
    antes = [{"name": "Caixa X", "cost": 2.5, "quantity": 1, "source": "steam"}]
    pos, resumo = inventario.mesclar(antes, _inv("Caixa X", qtd=3))
    assert pos[0]["cost"] == 2.5 and pos[0]["quantity"] == 3
    assert resumo["atualizados"] == 1


def test_mesclar_item_que_sumiu_fica_se_tem_valor_pago():
    """Relato de 16/11: anunciar no Mercado tira o item do inventário
    público, e a sincronização apagava o valor pago (regra de 15/11,
    "sumiu = vendeu"). Agora o item com valor pago fica, marcado; o sem
    valor pago sai (não perde nada e volta sozinho)."""
    antes = [{"name": "Anunciado", "cost": 100.0, "quantity": 1, "source": "steam"},
             {"name": "Sem valor", "cost": None, "quantity": 1, "source": "steam"},
             {"name": "Fica", "cost": 5.0, "quantity": 1, "source": "steam"}]
    pos, resumo = inventario.mesclar(antes, _inv("Fica"), agora=50.0)
    assert [(p["name"], p.get("fora_desde")) for p in pos] == [
        ("Anunciado", 50.0), ("Fica", None)]
    assert pos[0]["cost"] == 100.0
    assert resumo["removidos"] == 1 and resumo["fora"] == 1
    # Dia seguinte, ainda fora: a data de quando saiu não muda.
    pos, _ = inventario.mesclar(pos, _inv("Fica"), agora=90.0)
    assert pos[0]["fora_desde"] == 50.0
    # Anúncio cancelado: o item volta com o valor pago e sem a marca.
    pos, resumo = inventario.mesclar(pos, _inv("Fica", "Anunciado"), agora=99.0)
    volta = [p for p in pos if p["name"] == "Anunciado"]
    assert len(volta) == 1 and volta[0]["cost"] == 100.0 and "fora_desde" not in volta[0]


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


def test_conta_vazia_buscando_mostra_so_uma_mensagem(client):
    """Revisão de 16/11: "Buscando…" e "Nenhum item ainda" juntos se
    contradiziam na primeira visita."""
    import time
    sid = "76561198000000004"
    user_store.save_user_json(sid, "inventario_sync", {
        "em_andamento": True, "iniciado_ts": time.time()})
    _logado(client, sid)
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Buscando seu inventário" in pagina
    assert "Nenhum item ainda" not in pagina
    user_store.save_user_json(sid, "inventario_sync", {"status": "ok", "ts": time.time()})
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Nenhum item ainda" in pagina


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
    # As 4 que saíram (anunciadas ou vendidas) ficam fora do inventário,
    # com o valor pago (revisão 16/11).
    pos, _ = inventario.mesclar(lotes, _inv("Caixa X", qtd=1), agora=60.0)
    assert [(p["quantity"], p["cost"], p.get("fora_desde")) for p in pos] == [
        (1, 5.0, None), (3, 2.0, 60.0), (1, 5.0, 60.0)]
    assert pos[0]["lote"] == "b"
    # Anúncio cancelado: voltam primeiro as que estavam fora, com o valor.
    pos, _ = inventario.mesclar(pos, _inv("Caixa X", qtd=5), agora=70.0)
    assert sorted((p["quantity"], p["cost"]) for p in pos if not p.get("fora_desde")) == [
        (1, 5.0), (1, 5.0), (3, 2.0)]
    assert not [p for p in pos if p.get("fora_desde")]
    # Lote sem valor sai antes dos com valor.
    com_sem = lotes + [{"name": "Caixa X", "cost": None, "quantity": 1,
                        "source": "steam", "lote": "c", "added_ts": 3}]
    pos, _ = inventario.mesclar(com_sem, _inv("Caixa X", qtd=5))
    assert [p["lote"] for p in pos] == ["a", "b"]
    # Saiu tudo: os lotes com valor pago ficam, marcados.
    pos, resumo = inventario.mesclar(lotes, [], agora=80.0)
    assert [p.get("fora_desde") for p in pos] == [80.0, 80.0] and resumo["fora"] == 2
    pos, resumo = inventario.mesclar(com_sem, [], agora=80.0)
    assert [p["lote"] for p in pos] == ["a", "b"] and resumo["removidos"] == 1


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


# ── Item fora do inventário (revisão 16/11) ───────────────────────────

def test_conta_mostra_item_fora_do_inventario_com_vendi(client):
    sid = "76561198000000031"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa F", "cost": 3.0, "quantity": 1, "source": "steam",
         "fora_desde": 1_794_800_000.0},
        {"name": "Caixa G", "cost": 3.0, "quantity": 1, "source": "steam"}])
    import time
    inventario._gravar_estado(sid, {"status": steam_api.INV_OK, "ts": time.time(),
                                    "ultimo_ok_ts": time.time()})
    _logado(client, sid)
    pagina = client.get("/conta").data.decode("utf-8")
    assert pagina.count("linha-fora") == 1
    assert "Não está no seu inventário da Steam desde" in pagina
    assert "Anunciou no Mercado ou vendeu?" in pagina
    assert "Está anunciado no Mercado</label>" in pagina
    assert 'name="sell_price"' in pagina
    assert "1 item não aparece no inventário agora" in pagina


def test_anunciado_fica_e_vendi_vai_para_o_historico(client):
    """Pedido do usuário (16/11): uma caixa "anunciado" (fica até a pessoa
    tirar) e "Vendi" (não apaga: vai para o Histórico, com o lucro)."""
    import re
    from lodout.public_site import user_vendidos
    sid = "76561198000000034"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa V", "cost": 10.0, "quantity": 3, "source": "steam",
         "fora_desde": 1_794_800_000.0},
        {"name": "Caixa N", "cost": 1.0, "quantity": 1, "source": "steam"}])
    _logado(client, sid)
    pagina = client.get("/conta").data.decode("utf-8")
    token = re.search(r'name="csrf_token" value="([^"]+)"', pagina).group(1)
    # Item que está no inventário não pode ser marcado.
    client.post("/conta/posicoes/Caixa N/anunciado", data={"csrf_token": token, "anunciado": "1"})
    assert not any(p.get("anunciado") for p in user_portfolio.load_positions(sid))
    client.post("/conta/posicoes/Caixa V/anunciado", data={"csrf_token": token, "anunciado": "1"})
    pagina = client.get("/conta").data.decode("utf-8")
    assert "Anunciado no Mercado (fora do inventário desde" in pagina
    assert 'data-enviar-ao-mudar checked' in pagina
    # Vendeu 2 de 3 por R$ 20 cada: 1 fica, a venda vai para o histórico.
    r = client.post("/conta/posicoes/Caixa V/vendido",
                    data={"csrf_token": token, "sell_price": "20,00", "quantidade": "2"})
    assert r.status_code == 302
    v = [p for p in user_portfolio.load_positions(sid) if p["name"] == "Caixa V"]
    assert len(v) == 1 and v[0]["quantity"] == 1 and v[0]["anunciado"] is True
    vendas = user_vendidos.load(sid)
    assert len(vendas) == 1 and vendas[0]["quantity"] == 2 and vendas[0]["buy_cost"] == 10.0
    assert vendas[0]["pnl"] == round(2 * (20 / 1.15) - 20, 2)
    assert not __import__("lodout.public_site.user_trades", fromlist=["x"]).load_trades(sid)
    hist = client.get("/conta/historico").data.decode("utf-8")
    assert "Itens vendidos" in hist and "Caixa V" in hist and "+R$ 14,78" in hist
    # Preço inválido não vende nada.
    client.post("/conta/posicoes/Caixa V/vendido",
                data={"csrf_token": token, "sell_price": "abc", "quantidade": "1"})
    assert len(user_vendidos.load(sid)) == 1
    # Apagar a venda (marcada por engano).
    client.post("/conta/historico/vendidos/0/remover", data={"csrf_token": token})
    assert user_vendidos.load(sid) == []
    # Voltou ao inventário (anúncio cancelado): some a marca e o "anunciado".
    pos, _ = inventario.mesclar(user_portfolio.load_positions(sid), _inv("Caixa V", "Caixa N"))
    v = [p for p in pos if p["name"] == "Caixa V"][0]
    assert "fora_desde" not in v and "anunciado" not in v and v["cost"] == 10.0


def test_juntar_lotes_deixa_de_fora_o_que_saiu_do_inventario():
    sid = "76561198000000032"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa J", "cost": 2.0, "quantity": 1, "source": "steam", "lote": "a"},
        {"name": "Caixa J", "cost": 4.0, "quantity": 1, "source": "steam", "lote": "b"},
        {"name": "Caixa J", "cost": 9.0, "quantity": 1, "source": "steam", "lote": "c",
         "fora_desde": 5.0}])
    assert user_portfolio.juntar(sid, "Caixa J") == "ok"
    pos = user_portfolio.load_positions(sid)
    assert sorted((p["quantity"], p["cost"], bool(p.get("fora_desde"))) for p in pos) == [
        (1, 9.0, True), (2, 3.0, False)]


def test_recuperar_posicoes_do_backup(capsys):
    """Os valores apagados antes da correção voltam do backup diário."""
    import sqlite3
    from lodout import _paths
    from lodout.public_site import db as site_db, recuperar_posicoes
    sid = "76561198000000033"
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Anunciado", "cost": 50.0, "quantity": 2, "source": "steam"},
        {"name": "Voltou sem valor", "cost": 7.0, "quantity": 1, "source": "steam"},
        {"name": "Fica", "cost": 1.0, "quantity": 1, "source": "steam"}])
    pasta = Path(_paths.DATA_DIR) / "backups"
    pasta.mkdir(parents=True, exist_ok=True)
    origem = site_db.connect(None)
    destino = sqlite3.connect(str(pasta / "public_site-20261115-120000.db"))
    origem.backup(destino)
    origem.close(); destino.close()
    # A sincronização antiga apagou "Anunciado"; "Voltou sem valor" voltou sem o valor.
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Voltou sem valor", "cost": None, "quantity": 1, "source": "steam"},
        {"name": "Fica", "cost": 1.0, "quantity": 1, "source": "steam"}])
    assert recuperar_posicoes.main([sid]) == 0
    assert "Nada foi gravado" in capsys.readouterr().out
    assert len(user_portfolio.load_positions(sid)) == 2
    assert recuperar_posicoes.main([sid, "--aplicar"]) == 0
    pos = {p["name"]: p for p in user_portfolio.load_positions(sid)}
    assert pos["Anunciado"]["cost"] == 50.0 and pos["Anunciado"]["quantity"] == 2
    assert pos["Anunciado"].get("fora_desde")
    assert pos["Voltou sem valor"]["cost"] == 7.0
    assert pos["Fica"]["cost"] == 1.0
    assert list(pasta.glob(f"recuperacao-{sid}-*.json"))
    # Rodar de novo não duplica.
    assert recuperar_posicoes.main([sid, "--aplicar"]) == 0
    assert len(user_portfolio.load_positions(sid)) == 3
    assert recuperar_posicoes.main(["--todos"]) == 0
    assert "Nada a recuperar" in capsys.readouterr().out
