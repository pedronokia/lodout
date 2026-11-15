"""Catálogo amplo (plans/pending/catalogo-grande.md) -- sem rede: a busca da
Steam é sempre substituída por uma função falsa."""
from __future__ import annotations

import pytest

from lodout import steam_api
from lodout.public_site import catalogo, worker


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
