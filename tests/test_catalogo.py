"""Catálogo amplo (plans/archive/catalogo-grande.md) -- sem rede: a busca da
Steam é sempre substituída por uma função falsa."""
from __future__ import annotations

import pytest

from lodout import steam_api
from lodout.public_site import catalogo, worker


@pytest.fixture(autouse=True)
def _sem_sobreposicao(monkeypatch):
    # Os testes de paginação usam páginas de 2 itens; a sobreposição de 1
    # item tem teste próprio.
    monkeypatch.setattr(catalogo, "_SOBREPOSICAO", 0)


@pytest.fixture(autouse=True)
def _catalogo_limpo():
    for caminho in (catalogo._caminho_banco(), catalogo._caminho_estado()):
        for extra in ("", "-wal", "-shm"):
            p = caminho.with_name(caminho.name + extra)
            if p.exists():
                p.unlink()
    steam_api._rate_limit_state.clear()
    yield
    steam_api._rate_limit_state.clear()


@pytest.fixture
def sem_pausa(monkeypatch):
    monkeypatch.setattr(steam_api, "RATE_LIMIT_DELAY_S", 0.0)


def _linha(nome, preco=1.0, a_venda=10, cor="4b69ff", icon="h"):
    return {"hash_name": nome, "name": nome, "price": preco,
            "listings": a_venda, "name_color": cor, "icon": icon}


def _busca_falsa(paginas_por_tag, chamadas):
    """paginas_por_tag: {tag: [lista de itens]}; pagina de 2 em 2."""
    def fake(facets=None, sort="quantity", descending=True, start=0,
             count=100, **_):
        tag = facets["type"]
        chamadas.append((tag, start, sort, descending))
        itens = paginas_por_tag.get(tag, [])
        return steam_api.SEARCH_OK, itens[start:start + 2], len(itens)
    return fake


def test_gravar_deriva_categoria_raridade_exterior_versao_e_busca():
    conn = catalogo.conectar()
    catalogo.gravar(conn, "Rifles", [
        _linha("StatTrak™ AK-47 | Redline (Field-Tested)", cor="D2D2D2"),
        _linha("★ Karambit | Fade (Factory New)", cor="eb4b4b"),
    ])
    catalogo.gravar(conn, "Caixas e cápsulas", [
        _linha("Copenhagen 2024 Legends Autograph Capsule"),
        _linha("Snakebite Case"),
    ])
    linhas = {r["nome"]: r for r in conn.execute("SELECT * FROM itens")}
    ak = linhas["StatTrak™ AK-47 | Redline (Field-Tested)"]
    assert (ak["categoria"], ak["exterior"], ak["versao"]) == ("Rifles", "ft", "stattrak")
    assert "testada em campo" in ak["busca"] and "ak47" in ak["busca"]
    assert linhas["★ Karambit | Fade (Factory New)"]["raridade"] == "dourado"
    assert linhas["Copenhagen 2024 Legends Autograph Capsule"]["categoria"] == "Cápsulas de autógrafo"
    assert linhas["Snakebite Case"]["categoria"] == "Caixas"
    assert "capsula" in linhas["Copenhagen 2024 Legends Autograph Capsule"]["busca"]
    assert catalogo.contar(conn) == 4
    conn.close()


def test_varrer_completa_todas_as_fatias(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Adesivos", "S")))
    chamadas = []
    monkeypatch.setattr(steam_api, "search_market", _busca_falsa({
        "R": [_linha(f"Rifle {i}") for i in range(3)],
        "S": [_linha("Sticker | X")],
    }, chamadas))
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "completa"
    assert estado["fatia"] is None and estado["ultima_completa_ts"]
    assert estado["itens_no_banco"] == 4
    assert estado["tamanho_pagina"] == 1
    # Ordem por nome (paginação estável) e posição avançando pelo que veio.
    assert chamadas == [("R", 0, "name", False), ("R", 2, "name", False),
                        ("S", 0, "name", False)]
    # Logo depois, a rodada está em dia: nenhuma consulta nova.
    chamadas.clear()
    assert catalogo.varrer(ate_ts=1e12)["motivo"] == "em_dia"
    assert chamadas == []


def test_varrer_para_no_bloqueio_e_nao_tenta_logo_depois(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append(start)
        if start == 0:
            return steam_api.SEARCH_OK, [_linha("A"), _linha("B")], 4
        return steam_api.SEARCH_RATE_LIMITED, [], 0

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "bloqueio"
    assert estado["start"] == 2 and estado["bloqueios"] == 1
    chamadas.clear()
    assert catalogo.varrer(ate_ts=1e12)["motivo"] == "esperando_apos_bloqueio"
    assert chamadas == []


def test_varrer_continua_de_onde_parou(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    chamadas = []
    monkeypatch.setattr(steam_api, "search_market", _busca_falsa(
        {"R": [_linha(f"Rifle {i}") for i in range(4)]}, chamadas))
    # Janela que acaba depois da 1a página.
    relogio = iter([0, 0, 0, 0, 10, 10, 10, 10] + [10] * 50)
    monkeypatch.setattr(catalogo.time, "time", lambda: next(relogio) + 1e9)
    estado = catalogo.varrer(ate_ts=1e9 + 5)
    assert estado["start"] == 2 and estado["motivo"] == "janela"
    monkeypatch.setattr(catalogo.time, "time", lambda: 2e9)
    estado = catalogo.varrer(ate_ts=3e9)
    assert estado["motivo"] == "completa"
    assert [c[1] for c in chamadas] == [0, 2]


def test_varrer_pagina_vazia_antes_do_fim_nao_avanca(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    monkeypatch.setattr(steam_api, "search_market",
                        lambda **_: (steam_api.SEARCH_OK, [], 500))
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "pagina_vazia"
    assert estado["start"] == 0 and estado["vazias"] == 1


def test_varrer_404_repetido_encerra_fatia_e_continua(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Adesivos", "S")))
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append((facets["type"], start))
        if facets["type"] == "R":
            return steam_api.SEARCH_NOT_FOUND, [], 0
        return steam_api.SEARCH_OK, [_linha("Adesivo | X")], 1

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert [c for c in chamadas if c[0] == "R"] == [("R", 0)] * 3
    assert chamadas[-1] == ("S", 0)
    # Uma fatia pulada por 404 nao é volta completa: o relógio antigo fica.
    assert estado["motivo"] == "incompleta_404"
    assert estado["fatia"] is None and estado["itens_no_banco"] == 1
    assert estado["erros"] == 3 and estado["erros_404_fatias"] == 1
    assert estado["erros_404_fatias_rodada"] == 1
    assert estado["erro_404_seguidos"] == 0
    assert "ultima_completa_ts" not in estado
    assert estado["fim_ultima_rodada_ts"]
    assert catalogo.resumo()["motivo"] == "incompleta_404"
    assert catalogo.resumo()["erros_404_fatias_rodada"] == 1


def test_varrer_404_isolado_nao_encerra_fatia(monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append(start)
        if len(chamadas) == 1:
            return steam_api.SEARCH_NOT_FOUND, [], 0
        return steam_api.SEARCH_OK, [_linha("Rifle | A")], 1

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert chamadas == [0, 0]
    assert estado["motivo"] == "completa"
    assert estado["erros"] == 1 and estado["erros_404_fatias"] == 0
    assert estado["erro_404_seguidos"] == 0
    assert estado["ultima_completa_ts"]


def test_varrer_404_em_todas_as_fatias_nao_marca_completa_e_espara(
        monkeypatch, sem_pausa):
    """25/11: chuva de 404 em todas as categorias terminou marcada como
    'completa' com 2960 itens. Rodada ruim nao renova o relogio e nao
    tenta de novo no proximo ciclo do worker."""
    monkeypatch.setattr(catalogo, "FATIAS",
                        (("Rifles", "R"), ("Pistolas", "P"), ("Facas", "K")))
    chamadas = []
    monkeypatch.setattr(
        steam_api, "search_market",
        lambda facets=None, start=0, **_: (
            chamadas.append((facets["type"], start))
            or (steam_api.SEARCH_NOT_FOUND, [], 0)))

    estado = catalogo.varrer(ate_ts=1e12)
    assert len(chamadas) == 9  # 3 tentativas em cada fatia
    assert estado["motivo"] == "incompleta_404"
    assert estado["erros_404_fatias"] == 3
    assert estado["erros_404_fatias_rodada"] == 3
    assert estado["itens_ultima"] == 0
    assert "ultima_completa_ts" not in estado
    assert estado["fim_ultima_rodada_ts"]

    # O worker chama de novo no ciclo seguinte: nada de requisição nova.
    assert catalogo.varrer(ate_ts=1e12)["motivo"] == "esperando_apos_404"
    assert len(chamadas) == 9

    # Depois da espera, tenta de novo (aqui sem espera pra não dormir no teste).
    monkeypatch.setattr(catalogo, "_ESPERA_APOS_404_S", 0.0)
    estado = catalogo.varrer(ate_ts=1e12)
    assert len(chamadas) == 18
    assert estado["motivo"] == "incompleta_404"
    assert estado["erros_404_fatias_rodada"] == 3  # contador da rodada, não total


def test_varrer_guarda_fatia_pulada_e_retoma_no_proximo_start(monkeypatch,
                                                              sem_pausa):
    """26/11: sem o start da falha, a volta seguinte refazia Rifles por 22 h."""
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Adesivos", "S")))
    monkeypatch.setattr(catalogo, "_ESPERA_APOS_404_S", 0.0)
    chamadas = []

    def fake(facets=None, start=0, **_):
        tag = facets["type"]
        chamadas.append((tag, start))
        if tag == "R":
            if start == 0:
                return steam_api.SEARCH_OK, [_linha("Rifle | A"),
                                             _linha("Rifle | B")], 3
            return steam_api.SEARCH_NOT_FOUND, [], 0
        return steam_api.SEARCH_OK, [_linha("Adesivo | X")], 1

    monkeypatch.setattr(steam_api, "search_market", fake)
    monkeypatch.setattr(steam_api, "ultimo_404_busca",
                        lambda: {"start": 2, "body": "<html>maintenance</html>",
                                 "ts": 1.0, "url": "u"})
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "incompleta_404"
    assert estado["retomar"]["fatia"] == 0
    assert estado["retomar"]["tag"] == "R"
    assert estado["retomar"]["start"] == 2
    assert [p["tag"] for p in estado["fatias_puladas"]] == ["R"]
    pulada = estado["fatias_puladas"][0]
    assert pulada["total"] == 3  # total da fatia não se perde no 404
    assert pulada["detalhe_404"]["body"] == "<html>maintenance</html>"
    assert catalogo.resumo()["retomar"]["start"] == 2
    assert catalogo.resumo()["fatias_puladas"][0]["detalhe_404"]["start"] == 2
    # O monitor do scan detecta rodada nova por este campo no /api/health.
    assert catalogo.resumo()["inicio_ts"] == estado["inicio_ts"]

    chamadas.clear()
    catalogo.varrer(ate_ts=1e12)
    assert chamadas[0] == ("R", 2)  # não volta ao start 0


def test_retomar_legado_pula_fatia_ja_coletada(monkeypatch, sem_pausa):
    """Estado de 25/11 não tinha `retomar`: usa `totais` como ponto inicial."""
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Adesivos", "S")))
    catalogo._salvar_estado({
        "fatia": None, "start": 0, "motivo": "incompleta_404",
        "erros_404_fatias": 10, "erros_404_fatias_rodada": 10,
        "totais": {"Rifles": 2960}, "itens_rodada": 2960,
        "ultima_completa_ts": 1.0, "fim_ultima_rodada_ts": 2.0,
    })
    previa = catalogo.resumo()
    assert previa["retomar"]["start"] == 2960
    assert previa["retomar"]["origem"] == "legado"
    assert previa["fatias_puladas"] == []
    chamadas = []

    def fake(facets=None, start=0, **_):
        tag = facets["type"]
        chamadas.append((tag, start))
        if tag == "R":
            return steam_api.SEARCH_OK, [], 2960
        return steam_api.SEARCH_OK, [_linha("Adesivo | X")], 1

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert chamadas == [("R", 2960), ("S", 0)]
    assert estado["motivo"] == "completa"
    assert estado["retomar"] is None
    assert estado["fatias_puladas"] == []


def test_worker_so_varre_com_catalogo_ligado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(catalogo, "varrer",
                        lambda ate_ts, deve_parar: chamadas.append(ate_ts))
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    worker._esperar(3600)
    assert chamadas == []
    monkeypatch.setenv("LODOUT_CATALOGO", "1")
    worker._esperar(3600)
    assert len(chamadas) == 1
    # Steam bloqueando a coleta (permitido=False): nada de catálogo.
    worker._esperar(3600, permitido=False)
    # Janela curta demais (menos que a folga): nada de catálogo.
    worker._esperar(60)
    assert len(chamadas) == 1


def test_health_mostra_o_catalogo(monkeypatch, sem_pausa):
    from lodout.public_site.server import create_app
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    monkeypatch.setattr(steam_api, "search_market", _busca_falsa(
        {"R": [_linha("Rifle 1")]}, []))
    catalogo.varrer(ate_ts=1e12)
    app = create_app()
    app.config["TESTING"] = True
    dados = app.test_client().get("/api/health").get_json()
    assert dados["catalogo"]["itens_no_banco"] == 1
    assert dados["catalogo"]["motivo"] == "completa"


# ── Fase 2: o site lê o catálogo ─────────────────────────────────────

def _catalogo_com(*linhas_por_fatia):
    conn = catalogo.conectar()
    for fatia, itens in linhas_por_fatia:
        catalogo.gravar(conn, fatia, itens)
    conn.close()


def test_consultar_busca_filtros_e_ordem():
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Redline (Field-Tested)", preco=50.0, a_venda=300),
        _linha("AK-47 | Redline (Minimal Wear)", preco=90.0, a_venda=80),
        _linha("M4A4 | Howl (Field-Tested)", preco=9000.0, a_venda=5, cor="e4ae39"),
    ]))
    total, itens = catalogo.consultar({"busca": "redline ak"})
    assert total == 2
    assert [i["nome"] for i in itens][0] == "AK-47 | Redline (Field-Tested)"  # mais à venda
    total, itens = catalogo.consultar({"busca": "redline"}, ordenar="preco")
    assert [i["preco"] for i in itens] == [50.0, 90.0]
    assert catalogo.consultar({"exterior": "mw"})[0] == 1
    assert catalogo.consultar({"preco_max": 60})[0] == 1
    assert catalogo.consultar({"busca": "redline"},
                              excluir=["AK-47 | Redline (Field-Tested)"])[0] == 1
    assert catalogo.contar_por_categoria({"busca": "ak"}) == {"Rifles": 2}
    assert catalogo.precos(["M4A4 | Howl (Field-Tested)", "Nada"]) == {
        "M4A4 | Howl (Field-Tested)": 9000.0}


def test_consultar_sem_banco_volta_vazio():
    assert catalogo.consultar({"busca": "x"}) == (0, [])
    assert catalogo.item("x") is None and catalogo.precos(["x"]) == {}
    assert catalogo.tem_dados() is False


@pytest.fixture
def client(monkeypatch, tmp_path):
    from lodout import scan_store
    from lodout.public_site.server import create_app
    original = scan_store.load_last_scan
    p = tmp_path / "scanner_last.json"
    scan_store.save_last_scan("Todas", [
        {"name": "AK-47 | Redline (Field-Tested)", "score": 80, "price": 50.0,
         "case_label": "", "pump_risk": {"level": "low"}, "breakdown": [],
         "category": "Rifles"},
        {"name": "Item Arriscado", "score": 90, "price": 5.0, "case_label": "",
         "pump_risk": {"level": "high"}, "breakdown": [], "category": "Rifles"},
    ], path=p)
    monkeypatch.setattr(scan_store, "load_last_scan", lambda: original(path=p))
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_home_sem_busca_fica_igual(client):
    _catalogo_com(("Rifles", [_linha("AK-47 | Fire Serpent (Field-Tested)")]))
    body = client.get("/").data.decode("utf-8")
    assert "Fire Serpent" not in body
    assert "selo-sem-nota" not in body


def test_busca_traz_itens_com_nota_e_depois_o_catalogo(client):
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Redline (Field-Tested)", preco=51.0, a_venda=999),
        _linha("AK-47 | Redline (Minimal Wear)", preco=90.0, a_venda=50),
        _linha("Item Arriscado", preco=5.0),
    ]))
    body = client.get("/?q=redline").data.decode("utf-8")
    com_nota = body.index('data-nome="AK-47 | Redline (Field-Tested)"')
    divisor = body.index('class="divisor-catalogo"')
    assert com_nota < divisor < body.index('data-nome="AK-47 | Redline (Minimal Wear)"')
    # O item com nota não se repete como "sem nota", e o escondido por
    # risco alto não aparece pelo catálogo.
    assert body.count('data-nome="AK-47 | Redline (Field-Tested)"') == 1
    assert 'data-nome="Item Arriscado"' not in body
    assert "Mostrando 1–2 de 2 itens" in body


def test_busca_pagina_atravessa_nota_e_catalogo(client):
    _catalogo_com(("Rifles", [_linha(f"AK-47 | Redline X{i:02d}", a_venda=100 - i)
                              for i in range(20)]))
    p1 = client.get("/?q=redline").data.decode("utf-8")
    assert "Mostrando 1–12 de 21 itens" in p1
    p2 = client.get("/?q=redline&pagina=2").data.decode("utf-8")
    assert "Mostrando 13–21 de 21 itens" in p2
    # Página 1: 1 item com nota + 11 do catálogo (X00..X10).
    assert 'data-nome="AK-47 | Redline X10"' in p1
    assert 'data-nome="AK-47 | Redline X11"' in p2
    assert 'data-nome="AK-47 | Redline X19"' in p2
    assert 'data-nome="AK-47 | Redline X10"' not in p2


def test_nota_minima_mostra_so_itens_com_nota(client):
    _catalogo_com(("Rifles", [_linha("AK-47 | Redline (Minimal Wear)")]))
    body = client.get("/?q=redline&nota_min=10").data.decode("utf-8")
    assert 'data-nome="AK-47 | Redline (Minimal Wear)"' not in body


def test_pagina_de_item_so_do_catalogo(client):
    _catalogo_com(("Facas", [_linha("★ Karambit | Fade (Factory New)",
                                    preco=100.0, a_venda=7, cor="eb4b4b")]))
    r = client.get("/item/★ Karambit | Fade (Factory New)")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "Sem nota ainda" in body and "Por que ainda não tem nota?" in body
    assert "R$ 115,00" in body and "Venda mínima" in body  # simulador
    assert "raridade-dourado" in body
    # 21/11: mesmo simulador da página com nota; sem fila no catálogo, avisa
    # e nunca mostra a sugestão vazia (revisão 20/11: aparecia "…, , e %").
    assert "Simular compra" in body
    assert "Fila de encomendas da Steam não disponível" in body
    assert 'data-copiar-preco=""' not in body
    assert "copiar_preco.js" in body
    assert ", , e" not in body
    assert client.get("/item/Item Arriscado").status_code == 404
    assert client.get("/item/Nao Existe").status_code == 404


def test_conta_usa_preco_do_catalogo(client):
    from lodout.public_site import user_portfolio
    _catalogo_com(("Caixas e cápsulas", [_linha("Snakebite Case", preco=2.0)]))
    sid = "76561198000000077"
    user_portfolio.add_position(sid, "Snakebite Case", 1.0)
    with client.session_transaction() as s:
        s["steamid"] = sid
    body = client.get("/conta").data.decode("utf-8")
    # A célula diz de quando é o preço (dica ao passar o mouse).
    assert '<td role="cell" data-label="Vale hoje" class="celula-numero" title="Preço coletado ' in body
    assert '>R$ 2,00</td>' in body



def test_varrer_sobrepoe_um_item_entre_paginas(monkeypatch, sem_pausa):
    # 2026-11-15: a lista da Steam "escorrega" durante a varredura; cada
    # página começa 1 item antes do fim da anterior.
    monkeypatch.setattr(catalogo, "_SOBREPOSICAO", 1)
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append(start)
        itens = [_linha(f"Rifle {i:02d}") for i in range(25)]
        return steam_api.SEARCH_OK, itens[start:start + 10], 25

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "completa"
    assert chamadas == [0, 9, 18]
    assert estado["itens_no_banco"] == 25


def test_status_mostra_o_catalogo(client, monkeypatch, sem_pausa):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Adesivos", "S")))
    chamadas = []
    # Para no meio (bloqueio na 2a fatia): volta em andamento.
    def fake(facets=None, start=0, **_):
        if facets["type"] == "S":
            return steam_api.SEARCH_RATE_LIMITED, [], 0
        return steam_api.SEARCH_OK, [_linha("AK-47 | Redline (Field-Tested)")], 1
    monkeypatch.setattr(steam_api, "search_market", fake)
    catalogo.varrer(ate_ts=1e12)
    # A seção "Catálogo do Mercado" foi removida de /status a pedido do usuário.
    resumo = catalogo.resumo()
    assert resumo["itens_no_banco"] == 1
    assert resumo["bloqueios"] == 1
    body = client.get("/status").data.decode("utf-8")
    assert "Catálogo do Mercado" not in body


def test_status_sem_catalogo_nao_mostra_a_secao(client):
    assert "Catálogo do Mercado" not in client.get("/status").data.decode("utf-8")


def test_conta_lista_o_mais_valioso_primeiro(client):
    from lodout.public_site import user_portfolio
    _catalogo_com(("Rifles", [_linha("Barato", preco=1.0), _linha("Caro", preco=100.0),
                              _linha("Medio", preco=5.0)]))
    sid = "76561198000000078"
    for nome in ("Barato", "Caro", "Medio"):
        user_portfolio.add_position(sid, nome, None)
    with client.session_transaction() as s:
        s["steamid"] = sid
    body = client.get("/conta").data.decode("utf-8")
    assert body.index(">Caro<") < body.index(">Medio<") < body.index(">Barato<")
    assert 'data-total="falta_texto">3 itens<' in body
    assert "valem R$ 106,00 hoje" in body


def test_worker_completa_imagem_que_falta_pelo_catalogo():
    # Achado 2026-11-15: item novo no scan, sem coleta anterior e com o
    # preço do priceoverview, aparecia no ranking sem foto.
    from lodout.public_site import worker
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Safari Mesh (Battle-Scarred)", cor="b0c3d9", icon="hash-safari"),
    ]))
    novos = [
        {"name": "AK-47 | Safari Mesh (Battle-Scarred)", "icon": None},
        {"name": "Fora do catálogo", "icon": None},
        {"name": "Já tem", "icon": "outro"},
    ]
    assert worker._completar_metadados_do_catalogo(novos) == 1
    assert novos[0]["icon"] == "hash-safari"
    assert novos[0]["name_color"] == "b0c3d9"
    assert novos[1]["icon"] is None
    assert novos[2]["icon"] == "outro"


def test_catalogo_converte_dolar_para_reais_pela_cotacao_medida(monkeypatch):
    # Achado 2026-11-15: a busca do Mercado ignora currency=7 e devolve
    # dólar ("$5.19"); o site mostrava "R$ 5,19". A cotação vem dos itens
    # que estão na coleta (reais) e no catálogo (dólar).
    from lodout import scan_store
    catalogo.CAMBIO_FIXO = None
    catalogo._cambio_cache.update(ts=0.0, valor=None)
    nomes = [f"Item {i}" for i in range(12)]
    _catalogo_com(("Rifles", [_linha(n, preco=2.0 + i) for i, n in enumerate(nomes)]
                   + [_linha("So no catalogo", preco=5.19)]))
    # Na coleta, os mesmos itens custam 5,5x em reais (um ponto fora).
    resultados = [{"name": n, "price": round((2.0 + i) * 5.5, 2)} for i, n in enumerate(nomes)]
    resultados[0]["price"] = 999.0
    monkeypatch.setattr(scan_store, "load_last_scan", lambda: {"results": resultados})
    assert abs(catalogo.cambio() - 5.5) < 0.01
    assert catalogo.precos(["So no catalogo"]) == {"So no catalogo": round(5.19 * 5.5, 2)}
    assert catalogo.item("So no catalogo")["preco"] == round(5.19 * 5.5, 2)
    total, itens = catalogo.consultar({"busca": "so no catalogo"})
    assert itens[0]["preco"] == round(5.19 * 5.5, 2)
    # Filtro "até R$ 30": 5,19 dólares = R$ 28,55 entra; 
    total, _ = catalogo.consultar({"busca": "so no catalogo", "preco_max": 30})
    assert total == 1
    total, _ = catalogo.consultar({"busca": "so no catalogo", "preco_max": 20})
    assert total == 0
    # A última cotação boa fica salva como reserva.
    monkeypatch.setattr(scan_store, "load_last_scan", lambda: None)
    catalogo._cambio_cache.update(ts=0.0, valor=None)
    assert abs(catalogo.cambio() - 5.5) < 0.01


def test_catalogo_sem_cotacao_nao_mostra_preco(monkeypatch):
    from lodout import scan_store
    catalogo.CAMBIO_FIXO = None
    catalogo._cambio_cache.update(ts=0.0, valor=None)
    _catalogo_com(("Rifles", [_linha("Sozinho", preco=5.19)]))
    monkeypatch.setattr(scan_store, "load_last_scan", lambda: None)
    assert catalogo.cambio() is None
    assert catalogo.precos(["Sozinho"]) == {}
    assert catalogo.item("Sozinho")["preco"] is None


def test_status_mostra_a_cotacao(client, monkeypatch):
    from lodout import scan_store
    catalogo.CAMBIO_FIXO = None
    catalogo._cambio_cache.update(ts=0.0, valor=None)
    nomes = [f"Item {i}" for i in range(12)]
    _catalogo_com(("Rifles", [_linha(n, preco=2.0 + i) for i, n in enumerate(nomes)]))
    monkeypatch.setattr(scan_store, "load_last_scan", lambda: {"results": [
        {"name": n, "price": round((2.0 + i) * 5.62, 2)} for i, n in enumerate(nomes)]})
    import lodout.public_site.catalogo as c
    c._salvar_estado({"itens_no_banco": 12, "totais": {"Rifles": 12}, "fatia": 0, "start": 0})
    assert catalogo.resumo()["cotacao_brl_por_usd"] == 5.62
    body = client.get("/status").data.decode("utf-8")
    assert "Catálogo do Mercado" not in body


def test_parecidos_tira_palavras_do_fim_ate_achar():
    """Revisão 17/11: item não encontrado sugere parecidos."""
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Redline (Field-Tested)", a_venda=300),
        _linha("AK-47 | Redline (Minimal Wear)", a_venda=80),
        _linha("M4A4 | Howl (Field-Tested)", a_venda=5),
    ]))
    nomes = [r["nome"] for r in catalogo.parecidos("AK-47 | Redlin (Field Tested)")]
    assert nomes == ["AK-47 | Redline (Field-Tested)", "AK-47 | Redline (Minimal Wear)"]
    # "Redlinx" não casa: cai para só "ak47".
    assert len(catalogo.parecidos("AK-47 | Redlinx")) == 2
    assert catalogo.parecidos("Zzz qq") == []
    assert catalogo.parecidos("") == []


def test_item_nao_encontrado_diz_qual_e_sugere(client):
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Redline (Field-Tested)", preco=51.0, a_venda=999),
        _linha("AK-47 | Redline (Minimal Wear)", preco=90.0, a_venda=50),
    ]))
    r = client.get("/item/AK-47 | Redlin")
    body = r.data.decode("utf-8")
    assert r.status_code == 404
    assert "Não achamos esse item" in body and "“AK-47 | Redlin”" in body
    assert "Você quis dizer:" in body
    assert 'href="/item/AK-47%20%7C%20Redline%20(Minimal%20Wear)"' in body
    assert 'value="AK-47 | Redlin"' in body
    # Sem parecidos: só a busca, já preenchida.
    body = client.get("/item/Nada parecido").data.decode("utf-8")
    assert "Você quis dizer" not in body and "Tente parte do nome" in body
    # Outras páginas continuam com o texto de antes.
    assert "Essa página não existe" in client.get("/isso-nao-existe").data.decode("utf-8")


def test_busca_conta_o_catalogo_uma_vez_so(client, monkeypatch):
    """Revisão 17/11: a home contava o catálogo duas vezes por busca."""
    _catalogo_com(("Rifles", [
        _linha(f"AK-47 | Teste {i} (Field-Tested)", a_venda=100 - i) for i in range(30)]))
    contagens = []
    original = catalogo.consultar

    def espiao(*a, **k):
        contagens.append(k.get("contar", True))
        return original(*a, **k)
    monkeypatch.setattr(catalogo, "consultar", espiao)
    body = client.get("/?q=teste").data.decode("utf-8")
    assert contagens == [False]
    assert "AK-47 | Teste 0" in body
    # O total certo continua aparecendo na paginação (30 itens).
    body2 = client.get("/?q=teste&pagina=3").data.decode("utf-8")
    assert "AK-47 | Teste 29" in body2 or "AK-47 | Teste 2" in body2


def test_favicon_ico(client):
    """26/11: o ICO da marca oficial traz 16, 32 e 48 px, os três
    tamanhos usados por abas e marcadores no Windows."""
    import io
    from PIL import Image

    r = client.get("/favicon.ico")
    assert r.status_code == 200 and r.mimetype == "image/x-icon"
    assert "max-age=86400" in r.headers["Cache-Control"]
    ico = Image.open(io.BytesIO(r.data))
    assert sorted(ico.ico.sizes()) == [(16, 16), (32, 32), (48, 48)]


def test_sinonimos_busca_cobrem_facas_e_luvas_sem_knife_ou_gloves():
    """Plano de aprimoramento da busca (#10): 'faca karambit', 'faca bayonet',
    'faca shadow' e 'luva hand wraps' acham itens sem 'Knife'/'Gloves' no nome,
    inclusive em linhas já gravadas antes dos novos sinônimos."""
    _catalogo_com(
        ("Facas", [
            _linha("★ Karambit | Fade (Factory New)", preco=500.0, a_venda=5),
            _linha("★ Bayonet | Doppler (Factory New)", preco=300.0, a_venda=8),
            _linha("★ M9 Bayonet | Tiger Tooth (Factory New)", preco=400.0, a_venda=6),
            _linha("★ Shadow Daggers | Fade (Factory New)", preco=120.0, a_venda=12),
        ]),
        ("Luvas", [
            _linha("★ Hand Wraps | Cobalt Skull (Field-Tested)", preco=250.0, a_venda=4),
            _linha("★ Sport Gloves | Vice (Field-Tested)", preco=800.0, a_venda=2),
        ]),
        ("Rifles", [
            _linha("AK-47 | Redline (Field-Tested)", preco=20.0, a_venda=200),
        ]),
    )

    def nomes(q):
        _total, itens = catalogo.consultar({"busca": q}, limite=20)
        return {it["nome"] for it in itens}

    assert nomes("faca karambit") == {"★ Karambit | Fade (Factory New)"}
    assert nomes("facas bayonet") == {
        "★ Bayonet | Doppler (Factory New)",
        "★ M9 Bayonet | Tiger Tooth (Factory New)",
    }
    assert nomes("faca m9") == {"★ M9 Bayonet | Tiger Tooth (Factory New)"}
    assert nomes("adagas shadow") == {"★ Shadow Daggers | Fade (Factory New)"}
    assert nomes("faca shadow") == {"★ Shadow Daggers | Fade (Factory New)"}
    assert nomes("luva hand wraps") == {"★ Hand Wraps | Cobalt Skull (Field-Tested)"}
    assert nomes("luvas cobalt") == {"★ Hand Wraps | Cobalt Skull (Field-Tested)"}
    assert "AK-47 | Redline (Field-Tested)" not in nomes("faca")
    assert "★ Sport Gloves | Vice (Field-Tested)" not in nomes("faca")
    assert "★ Karambit | Fade (Factory New)" not in nomes("luva")

    # Simula linha legada no SQLite (gravada antes do sinônimo na coluna busca):
    # a consulta continua encontrando via categoria = 'Facas' / 'Luvas'.
    conn = catalogo.conectar()
    with conn:
        conn.execute(
            "UPDATE itens SET busca = '★ karambit | fade (factory new)' "
            "WHERE nome = '★ Karambit | Fade (Factory New)'"
        )
        conn.execute(
            "UPDATE itens SET busca = '★ hand wraps | cobalt skull (fieldtested)' "
            "WHERE nome = '★ Hand Wraps | Cobalt Skull (Field-Tested)'"
        )
    conn.close()
    assert nomes("faca karambit") == {"★ Karambit | Fade (Factory New)"}
    assert nomes("luva hand wraps") == {"★ Hand Wraps | Cobalt Skull (Field-Tested)"}


def test_consultar_escapa_coringas_like():
    """Plano de aprimoramento da busca (#11): %, _ e \\ em ?q= são literais."""
    _catalogo_com(("Rifles", [
        _linha("AK-47 | Redline (Field-Tested)", a_venda=500),
        _linha("AK-47 | Slate (Field-Tested)", a_venda=400),
        _linha("AK% Especial", a_venda=10),
        _linha("AK_Teste", a_venda=10),
        _linha("AKxTeste", a_venda=10),
        _linha("Item \\ Barra", a_venda=10),
    ]))
    _t, res_pct = catalogo.consultar({"busca": "ak%"})
    assert [r["nome"] for r in res_pct] == ["AK% Especial"]

    _t, res_sub = catalogo.consultar({"busca": "ak_teste"})
    assert [r["nome"] for r in res_sub] == ["AK_Teste"]

    _t, res_bar = catalogo.consultar({"busca": "item \\ barra"})
    assert [r["nome"] for r in res_bar] == ["Item \\ Barra"]


def test_consultar_ordenar_relevancia_prioriza_exato_e_prefixo():
    """Plano de aprimoramento da busca (#2): ordenar='relevancia' coloca nome
    exato e prefixo antes de itens mais anunciados (a_venda)."""
    linhas = [_linha(f"Gamma 2 Case Extra {i}", a_venda=5000 - i) for i in range(15)]
    linhas += [
        _linha("Gamma Case", a_venda=5),
        _linha("Gamma Case Especial", a_venda=12),
        _linha("Revolution Case", a_venda=8),
        _linha("Caixa Revolução Extra", a_venda=4000),
        _linha("★ Karambit | Fade (Factory New)", a_venda=3),
        _linha("★ Karambit | Fade (Minimal Wear)", a_venda=900),
    ]
    _catalogo_com(("Caixas e cápsulas", linhas))

    _t, res = catalogo.consultar(
        {"busca": "Gamma Case"}, ordenar="relevancia", limite=5, contar=False,
    )
    assert res[0]["nome"] == "Gamma Case"
    assert res[1]["nome"] == "Gamma Case Especial"

    # Match exato em português sem acento ("caixa revolucao" -> "Caixa Revolução")
    # vem antes de um item com prefixo igual e muito mais anúncios.
    _t, res_pt = catalogo.consultar(
        {"busca": "caixa revolucao"}, ordenar="relevancia", limite=5, contar=False,
    )
    assert res_pt[0]["nome"] == "Revolution Case"
    assert res_pt[1]["nome"] == "Caixa Revolução Extra"

    # Match exato sem a estrela ★ inicial
    _t, res_faca = catalogo.consultar(
        {"busca": "Karambit | Fade (Factory New)"},
        ordenar="relevancia", limite=5, contar=False,
    )
    assert res_faca[0]["nome"] == "★ Karambit | Fade (Factory New)"

    # Bordas: busca vazia ou só pontuação cai no fallback sem erro.
    assert catalogo.relevancia_busca("Gamma Case", "Caixa Gama", "   ") == 2
    assert catalogo._ordem_relevancia(" | ")[1] == []
    _t, res_vazio = catalogo.consultar({"busca": "   "}, ordenar="relevancia", limite=2, contar=False)
    assert len(res_vazio) == 2


def test_varrer_conta_paginas_curtas_e_pausa_apos_tres_seguidas(monkeypatch, sem_pausa):
    """Plano de aprimoramento da busca (#3): página menor que o tamanho cheio
    antes do fim da fatia conta em paginas_curta e pausa após 3 seguidas."""
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    respostas = iter([
        (steam_api.SEARCH_OK, [_linha(f"R{i}") for i in range(4)], 20),  # cheia (4)
        (steam_api.SEARCH_OK, [_linha("R4")], 20),                       # curta 1
        (steam_api.SEARCH_OK, [_linha("R5")], 20),                       # curta 2
        (steam_api.SEARCH_OK, [_linha("R6")], 20),                       # curta 3 -> pausa
        (steam_api.SEARCH_OK, [_linha("R7")], 20),                       # não deve chamar
    ])
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append(start)
        return next(respostas)

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert len(chamadas) == 4
    assert estado["motivo"] == "pagina_curta"
    assert estado["paginas_curta"] == 3
    assert estado["paginas_curta_rodada"] == 3
    assert estado["paginas_curta_seguidas"] == 3
    assert "ultima_completa_ts" not in estado
    res = catalogo.resumo()
    assert res["paginas_curta"] == 3 and res["paginas_curta_rodada"] == 3


def test_pausa_entre_paginas_escalona_para_404_e_pagina_curta_com_teto(monkeypatch):
    """Plano de aprimoramento da busca (#5): backoff limitado sem mexer no
    valor base de steam_api.RATE_LIMIT_DELAY_S."""
    monkeypatch.setattr(steam_api, "RATE_LIMIT_DELAY_S", 2.0)
    monkeypatch.delenv("LODOUT_CATALOGO_FATOR_PAUSA", raising=False)
    # base = 2.0 * 5.0 = 10.0
    assert catalogo._pausa_entre_paginas({}) == pytest.approx(10.0)
    assert catalogo._pausa_entre_paginas({"erro_404_seguidos": 1}) == pytest.approx(20.0)
    assert catalogo._pausa_entre_paginas({"erro_404_seguidos": 2}) == pytest.approx(40.0)
    assert catalogo._pausa_entre_paginas({"erro_404_seguidos": 5}) == pytest.approx(40.0)
    assert catalogo._pausa_entre_paginas({"paginas_curta_seguidas": 1}) == pytest.approx(20.0)
    assert steam_api.RATE_LIMIT_DELAY_S == 2.0


def test_varrer_registra_ordem_instavel_quando_sobreposicao_nao_bate(monkeypatch, sem_pausa):
    """Plano de aprimoramento da busca (#6): sem sobreposição esperada entre
    páginas consecutivas da mesma fatia, ordem_instavel é incrementado."""
    monkeypatch.setattr(catalogo, "_SOBREPOSICAO", 1)
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    paginas = iter([
        (steam_api.SEARCH_OK, [_linha("A"), _linha("B"), _linha("C")], 5),
        # Esperava sobreposição de 1 ("C"), mas vieram nomes totalmente novos:
        (steam_api.SEARCH_OK, [_linha("D"), _linha("E"), _linha("F")], 5),
    ])
    monkeypatch.setattr(steam_api, "search_market", lambda **_: next(paginas))
    estado = catalogo.varrer(ate_ts=1e12)
    assert estado["motivo"] == "completa"
    assert estado["ordem_instavel"] == 1
    assert estado["ordem_instavel_rodada"] == 1
    assert catalogo.resumo()["ordem_instavel"] == 1


def test_varrer_freio_404_em_start_zero_encerra_sem_queimar_todas_fatias(monkeypatch, sem_pausa):
    """Freio para 404 em start=0 (AGENTS.md): 3 fatias seguidas falhando na
    posição 0 encerram a rodada sem desperdiçar consultas nas demais."""
    monkeypatch.setattr(catalogo, "FATIAS", tuple((f"F{i}", f"T{i}") for i in range(6)))
    chamadas = []

    def fake(facets=None, start=0, **_):
        chamadas.append((facets["type"], start))
        return steam_api.SEARCH_NOT_FOUND, [], 0

    monkeypatch.setattr(steam_api, "search_market", fake)
    estado = catalogo.varrer(ate_ts=1e12)
    assert len(chamadas) == 9  # só 3 fatias x 3 tentativas (não 6 x 3 = 18)
    assert estado["motivo"] == "incompleta_404"
    assert estado["freio_404_start0"] is True
    assert estado["erros_404_fatias_rodada"] == 3
    assert estado["retomar"]["fatia"] == 0 and estado["retomar"]["start"] == 0
    assert catalogo.resumo()["freio_404_start0"] is True
    assert catalogo.varrer(ate_ts=1e12)["motivo"] == "esperando_apos_404"

