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
    assert "<strong>R$ 115,00</strong>" in body  # conta da revenda
    assert "raridade-dourado" in body
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
    body = client.get("/status").data.decode("utf-8")
    assert "Catálogo do Mercado" in body
    assert "<strong>1</strong> itens no catálogo" in body
    assert "Primeira volta em andamento" in body
    assert "Pausas pedidas pela Steam: 1" in body


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
    assert "R$ 5,62</strong> por dólar" in body and "medida em 12 itens" in body
