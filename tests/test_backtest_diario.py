"""Backtest diário da nota (backtest_diario.py + score_backtest.relatorio).
Sem rede: usa as cópias de página guardadas pela coleta."""
from __future__ import annotations

from lodout import scan_engine, scan_store, score_backtest
from lodout.public_site import backtest_diario, worker


def test_resumo_por_faixa_conta_quem_pagou_a_taxa():
    linhas = [
        {"score": 90, "retorno_pct": 30.0},
        {"score": 88, "retorno_pct": -5.0},
        {"score": 60, "retorno_pct": 10.0},
        {"score": 20, "retorno_pct": -1.0},
    ]
    r = score_backtest.resumo_por_faixa(linhas)
    assert r["85-100"] == {"n": 2, "mediana_pct": 12.5, "passou_taxa_pct": 50, "caiu_pct": 50}
    assert r["50-69"]["passou_taxa_pct"] == 0
    assert "70-84" not in r


def _hist(dias, subida_por_dia=0.0):
    t0 = 1_700_000_000 - (1_700_000_000 % 86400)
    return [{"time": t0 + d * 86400, "price_median": 10.0 + d * subida_por_dia,
             "purchases": 5} for d in range(dias)]


def test_relatorio_separa_horizontes_e_tipos():
    itens = [{"name": "AK-47 | Redline (Field-Tested)", "price_history": _hist(800, 0.01),
              "is_container": False},
             {"name": "Snakebite Case", "price_history": _hist(800, 0.0),
              "is_container": True}]
    rel = score_backtest.relatorio(itens, horizontes=(30, 365),
                                   agora=itens[0]["price_history"][-1]["time"])
    assert rel["itens"] == 2
    h = rel["horizontes"]["365"]
    assert h["itens_com_amostra"] == 2
    assert "skins" in h and "caixas" in h
    assert sum(f["n"] for f in h["faixas"].values()) == h["n"]


def test_rodar_se_preciso_usa_as_copias_guardadas_e_roda_1x_por_dia(monkeypatch, tmp_path):
    import shutil
    from lodout import _paths
    shutil.rmtree(_paths.DATA_DIR / "rodizio_paginas", ignore_errors=True)
    (_paths.DATA_DIR / "backtest_resultado.json").unlink(missing_ok=True)
    nome = "AK-47 | Redline (Field-Tested)"
    scan_engine._guardar_pagina(nome, {"price_history": _hist(500, 0.01)}, 1.0)
    monkeypatch.setattr(scan_store, "load_last_scan",
                        lambda: {"results": [{"name": nome}, {"name": "Sem copia"}]})
    assert backtest_diario.rodar_se_preciso() is True
    res = backtest_diario.ler()
    assert res["itens"] == 1 and "30" in res["horizontes"]
    assert backtest_diario.rodar_se_preciso() is False  # já rodou hoje


def test_worker_roda_o_backtest_so_com_a_chave_ligada(monkeypatch):
    chamadas = []
    monkeypatch.setattr(backtest_diario, "rodar_se_preciso",
                        lambda: chamadas.append(1))
    monkeypatch.setattr(worker.time, "sleep", lambda s: None)
    worker._esperar(3600)
    assert chamadas == []
    monkeypatch.setenv("LODOUT_BACKTEST_DIARIO", "1")
    worker._esperar(3600)
    assert chamadas == [1]


def test_health_mostra_o_backtest():
    from lodout import _paths
    _paths.atomic_write_text(_paths.DATA_DIR / "backtest_resultado.json",
                             '{"itens": 3, "ts": 1.0, "horizontes": {}}')
    from lodout.public_site.server import create_app
    app = create_app()
    dados = app.test_client().get("/api/health").get_json()
    assert dados["backtest"]["itens"] == 3
    (_paths.DATA_DIR / "backtest_resultado.json").unlink()
