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


def test_experimento_caixas_mede_variantes_e_restaura_os_fatores(monkeypatch):
    """Revisão das caixas (2026-11-16): variantes medidas só na parte de
    calibração; os fatores da nota voltam ao que eram depois."""
    from lodout import signals
    antes = (signals._REVERSAL_IN_CONTAINERS, signals._PRICE_LEVEL_ENABLED,
             signals._DRAWDOWN_AT_HIGH_ENABLED, signals._VINTAGE_BONUS_ENABLED)
    itens = [{"name": f"Caixa {i}", "price_history": _hist(500, 0.01 * (i % 3)),
              "is_container": True} for i in range(10)]
    itens += [{"name": "AK-47 | Redline (Field-Tested)", "price_history": _hist(500, 0.01),
               "is_container": False}]
    r = backtest_diario.experimento_caixas(itens)
    assert r["caixas_calibracao"] == 7 and r["caixas_confirmacao"] == 3
    assert set(r["calibracao"]) == {n for n, _ in backtest_diario._CAIXAS_VARIANTES}
    assert "confirmacao" not in r  # só depois de escolher
    assert (signals._REVERSAL_IN_CONTAINERS, signals._PRICE_LEVEL_ENABLED,
            signals._DRAWDOWN_AT_HIGH_ENABLED, signals._VINTAGE_BONUS_ENABLED) == antes
    monkeypatch.setattr(backtest_diario, "_CAIXAS_CONFIRMAR", "sem_nivel_de_preco")
    r = backtest_diario.experimento_caixas(itens)
    assert r["confirmacao"]["variante"] == "sem_nivel_de_preco"
    assert set(r["confirmacao"]) == {"variante", "atual", "sem_nivel_de_preco"}


def test_experimento_das_caixas_nao_roda_no_worker_por_padrao(monkeypatch):
    """16/11: dentro do worker o experimento não terminou em 2 h e segurou
    a coleta; o backtest do dia roda sem ele, a não ser que ligado."""
    from lodout.public_site import backtest_diario
    chamado = []
    monkeypatch.setattr(backtest_diario, "montar_itens", lambda: [{"x": 1}])
    monkeypatch.setattr(backtest_diario.score_backtest, "relatorio", lambda itens, **_: {"itens": 1})
    monkeypatch.setattr(backtest_diario, "experimento_caixas", lambda itens: chamado.append(1) or {})
    monkeypatch.delenv("LODOUT_EXPERIMENTO_CAIXAS", raising=False)
    assert backtest_diario.rodar_se_preciso() is True
    assert chamado == [] and "experimento_caixas" not in backtest_diario.ler()


def _itens_sinteticos(n=6, seed=3):
    import math
    import random
    rng = random.Random(seed)
    agora = 1_794_900_000.0
    itens = []
    for k in range(n):
        p = rng.uniform(1, 50)
        hist = []
        t = agora - 3 * 365 * 86400
        while t < agora:
            p *= math.exp(rng.gauss(0, 0.03))
            hist.append({"time": t, "price_median": round(p, 2)})
            t += 86400
        rng.shuffle(hist)  # a ordem do histórico não pode mudar o resultado
        itens.append({"name": f"Caixa {k}" if k % 2 else f"AK-47 | Teste {k} (Field-Tested)",
                      "price_history": hist, "is_container": bool(k % 2)})
    return itens, agora


def test_relatorio_calcula_uma_vez_e_da_o_mesmo_que_amostras():
    """Revisão 17/11: o relatório reaproveita a nota de cada data entre os
    horizontes; as linhas têm que ser as mesmas de `amostras()`."""
    itens, agora = _itens_sinteticos()
    for h in (30, 90, 365):
        esperado = []
        for it in itens:
            esperado.extend(score_backtest.amostras(
                it["name"], it["price_history"], it["is_container"], h, agora=agora))
        obtido = []
        for it in itens:
            obtido.extend(score_backtest._linhas_do_item(it, (30, 90, 365), 30.0, agora)[h])
        chave = lambda r: (r["name"], r["as_of_ts"])
        assert sorted(esperado, key=chave) == sorted(obtido, key=chave)


def test_relatorio_mede_cada_fator_em_calibracao_e_confirmacao():
    itens, agora = _itens_sinteticos(n=10)
    rel = score_backtest.relatorio(itens, horizontes=(30,), agora=agora, fatores_seed=5)
    fat = rel["horizontes"]["30"]["fatores"]
    assert set(fat) == {"skins", "caixas"}
    for grupo in fat.values():
        assert set(grupo) == {"calibracao", "confirmacao"}
    blocos = [b for g in fat.values() for parte in g.values() for b in parte.values()]
    assert blocos, "esperava ao menos um fator medido"
    for b in blocos:
        assert {"com", "sem"} <= set(b) and b["com"]["n"] >= 20
    # Sem a semente, o relatório fica como antes.
    assert "fatores" not in score_backtest.relatorio(
        itens, horizontes=(30,), agora=agora)["horizontes"]["30"]


def test_teste_para_frente_usa_a_nota_que_o_site_mostrou():
    """22/11: nota de verdade (notas_historico) x preço 30 dias depois."""
    from lodout.public_site import notas_historico
    t0 = 1_700_000_000 - (1_700_000_000 % 86400)
    hist_sobe = [{"time": t0 + d * 86400, "price_median": 10.0 + d * 0.1}
                 for d in range(80)]
    hist_cai = [{"time": t0 + d * 86400, "price_median": 20.0 - d * 0.1}
                for d in range(80)]
    for d in range(40):
        notas_historico.gravar_snapshot(
            {"ts": t0 + d * 86400 + 3600, "items": [
                {"name": "Sobe", "score": 90, "position": 1},
                {"name": "Cai", "score": 30, "position": 2}]},
            agora=t0 + d * 86400 + 3600)
    itens = [{"name": "Sobe", "price_history": hist_sobe},
             {"name": "Cai", "price_history": hist_cai}]
    r = backtest_diario.teste_para_frente(itens, 30, agora=t0 + 79 * 86400)
    assert r["itens"] == 2 and r["pares"] >= 30
    assert r["spearman"] > 0.8  # só duas notas distintas: o máximo é ~0,87
    assert r["faixas"]["85-100"]["mediana_pct"] > 0 > r["faixas"]["0-49"]["mediana_pct"]
    assert r["pesos_mudaram_em"] == "2026-11-22"


def test_teste_para_frente_sem_30_dias_so_diz_quando():
    from lodout.public_site import notas_historico
    agora = 1_700_000_000.0
    notas_historico.gravar_snapshot(
        {"ts": agora - 5 * 86400, "items": [{"name": "X", "score": 50, "position": 1}]},
        agora=agora - 5 * 86400)
    r = backtest_diario.teste_para_frente(
        [{"name": "X", "price_history": [{"time": agora - 5 * 86400, "price_median": 1.0}]}],
        30, agora=agora)
    assert r["pares"] == 0 and "spearman" not in r
    assert r["primeiro_resultado_ts"] == agora - 5 * 86400 + 30 * 86400
