"""Backtest diário da nota, no servidor e sem consultar a Steam.

Pergunta: no passado, itens com nota alta subiram mais que os de nota
baixa -- a ponto de pagar a taxa de 15% da Steam? Usa as cópias da página
de cada item que a coleta já guarda (`data/rodizio_paginas/`, histórico
completo de preço) e `score_backtest.relatorio()` (replay sem lookahead).
Resultado em `data/backtest_resultado.json`, no `/api/health` -> backtest.

Limites de leitura (ver score_backtest.py): a amostra são os itens que o
site acompanha HOJE (populares, sobreviventes -- viés de seleção), o
livro de ofertas não tem histórico, e passado não garante futuro.
"""
from __future__ import annotations

import json
import logging
import time

from lodout import _paths, cases, scan_engine, scan_store, score_backtest

_logger = logging.getLogger(__name__)
INTERVALO_S = 24 * 3600
# Medição por fator (revisão 17/11): a faixa 85-100 teve o pior resultado
# a 1 ano. Split fixo por item -- hipóteses saem da calibração (70%), o
# que se reporta é a confirmação (30%). Só mede; não muda a nota.
_FATORES_SEED = 20261117


def _caminho():
    return _paths.DATA_DIR / "backtest_resultado.json"


def ler() -> dict:
    dados = _paths.load_json_record(_caminho(), {})
    return dados if isinstance(dados, dict) else {}


def ligado() -> bool:
    from lodout._ambiente import ambiente
    return (ambiente("BACKTEST_DIARIO") or "").strip().lower() in ("1", "true", "sim")


def _experimento_ligado() -> bool:
    from lodout._ambiente import ambiente
    return (ambiente("EXPERIMENTO_CAIXAS") or "").strip().lower() in ("1", "true", "sim")


def montar_itens() -> "list[dict]":
    scan = scan_store.load_last_scan() or {}
    itens = []
    for r in scan.get("results") or []:
        nome = r.get("name")
        guardada = scan_engine._ler_pagina_guardada(nome) if nome else None
        hist = (guardada[1] or {}).get("price_history") if guardada else None
        if hist:
            itens.append({"name": nome, "price_history": hist,
                          "is_container": cases.is_container(nome)})
    return itens


# ── Revisão da nota das caixas (2026-11-16) ──────────────────────────
# O backtest diário mostrou que a nota quase não ordena caixas a 30 e 90
# dias. Variantes e regra de decisão registradas ANTES de ver os dados:
# - split fixo por item (score_backtest.split_itens, seed abaixo): 70% das
#   caixas calibram, 30% confirmam;
# - variantes medidas só na calibração;
# - uma variante só ganha se melhorar o Spearman das caixas em pelo menos
#   2 dos 3 horizontes (30, 90, 365 d) sem piorar o de 365 d em mais de
#   0,02;
# - a escolhida roda UMA vez na confirmação (_CAIXAS_CONFIRMAR); o número
#   da confirmação é o que se reporta, sem ajustar depois de vê-lo.
# Nada disto muda a nota do site: só mede.
_CAIXAS_SEED = 20261116
_CAIXAS_VARIANTES = (
    ("atual", {}),
    ("reversao_em_caixas", {"_REVERSAL_IN_CONTAINERS": True}),
    ("sem_nivel_de_preco", {"_PRICE_LEVEL_ENABLED": False}),
    ("sem_queda_do_topo", {"_DRAWDOWN_AT_HIGH_ENABLED": False}),
    ("bonus_de_idade", {"_VINTAGE_BONUS_ENABLED": True}),
)
# Nome da variante a confirmar (depois de ver a calibração), ou None.
_CAIXAS_CONFIRMAR: "str | None" = None


def _medir_variante(itens, mudancas: dict, horizontes=(30, 90, 365)) -> dict:
    from lodout import signals
    antes = {k: getattr(signals, k) for k in mudancas}
    try:
        for k, v in mudancas.items():
            setattr(signals, k, v)
        out = {}
        for h in horizontes:
            r = score_backtest.avaliar(itens, h)
            out[str(h)] = {"n": r["n"], "spearman": r["spearman"]}
        return out
    finally:
        for k, v in antes.items():
            setattr(signals, k, v)


def experimento_caixas(itens: "list[dict]") -> dict:
    calibracao, confirmacao = score_backtest.split_itens(itens, seed=_CAIXAS_SEED)
    cal = [i for i in calibracao if i.get("is_container")]
    conf = [i for i in confirmacao if i.get("is_container")]
    out = {"caixas_calibracao": len(cal), "caixas_confirmacao": len(conf),
           "calibracao": {}}
    for nome, mudancas in _CAIXAS_VARIANTES:
        out["calibracao"][nome] = _medir_variante(cal, mudancas)
    if _CAIXAS_CONFIRMAR:
        mud = dict(_CAIXAS_VARIANTES).get(_CAIXAS_CONFIRMAR)
        if mud is not None:
            out["confirmacao"] = {
                "variante": _CAIXAS_CONFIRMAR,
                "atual": _medir_variante(conf, {}),
                _CAIXAS_CONFIRMAR: _medir_variante(conf, mud),
            }
    return out


# Teste "para a frente" (22/11, pedido do usuário): o replay acima não
# consegue medir os fatores do livro de ofertas ("Fácil de comprar e
# vender" +25, "Mais gente querendo comprar" +20), que não têm histórico
# na Steam -- e são eles que mais pesam no Top 20 de hoje. Aqui a nota é
# a de VERDADE, a que o site mostrou naquele dia (notas_historico, desde
# 17/11), comparada com o preço `horizonte` dias depois (a mesma conta de
# retorno do replay: bruto, sem a taxa de 15%). Os pesos mudaram em 22/11
# (fatores "mediana" e "multi_period" de skins saíram): notas antes e
# depois disso não são a mesma régua. Pares do mesmo item em dias
# seguidos não são independentes: ler o Spearman com cuidado.
_PARA_FRENTE_HORIZONTES = (30,)
_PARA_FRENTE_MIN_PARES = 30
PESOS_MUDARAM_EM = "2026-11-22"


def teste_para_frente(itens: "list[dict]", horizonte_dias: int = 30,
                      agora: "float | None" = None) -> dict:
    from lodout.public_site import notas_historico
    agora = time.time() if agora is None else agora
    historico = {i["name"]: i["price_history"] for i in itens if i.get("price_history")}
    linhas, nomes, dias = [], set(), set()
    for nome, ts, nota in notas_historico.fotos_diarias(agora - horizonte_dias * 86400):
        ph = historico.get(nome)
        if not ph:
            continue
        ret = score_backtest.forward_return(ph, ts, horizonte_dias, tolerancia_dias=2.0)
        if ret is None:
            continue
        linhas.append({"score": nota, "retorno_pct": ret})
        nomes.add(nome)
        dias.add(int(ts // 86400))
    inicio = notas_historico.primeiro_ts_completo()
    out = {"horizonte_dias": horizonte_dias, "pares": len(linhas),
           "itens": len(nomes), "dias": len(dias),
           "notas_desde": inicio, "pesos_mudaram_em": PESOS_MUDARAM_EM}
    if inicio:
        out["primeiro_resultado_ts"] = inicio + horizonte_dias * 86400
    if len(linhas) >= _PARA_FRENTE_MIN_PARES:
        sp = score_backtest.spearman([r["score"] for r in linhas],
                                     [r["retorno_pct"] for r in linhas])
        out["spearman"] = round(sp, 3) if sp is not None else None
        out["faixas"] = score_backtest.resumo_por_faixa(linhas)
    return out


def rodar_se_preciso() -> bool:
    """Roda no máximo 1x por dia. True se rodou."""
    if time.time() - float(ler().get("ts") or 0) < INTERVALO_S:
        return False
    inicio = time.time()
    itens = montar_itens()
    if not itens:
        return False
    rel = score_backtest.relatorio(itens, fatores_seed=_FATORES_SEED)
    try:
        rel["para_frente"] = {str(h): teste_para_frente(itens, h)
                              for h in _PARA_FRENTE_HORIZONTES}
    except Exception:  # medir não pode derrubar o backtest do dia
        _logger.exception("Teste para a frente falhou")
    # O experimento das caixas saiu daqui (16/11): rodando dentro do worker,
    # ele não terminou em mais de 2 h e segurou a coleta e o Top 20 a tarde
    # toda (o backtest sem ele leva ~4 min). Só roda se ligado de propósito
    # (LODOUT_EXPERIMENTO_CAIXAS=1) -- melhor fora do worker.
    if _experimento_ligado():
        try:
            rel["experimento_caixas"] = experimento_caixas(itens)
        except Exception:  # medir não pode derrubar o backtest do dia
            _logger.exception("Experimento das caixas falhou")
    rel["ts"] = time.time()
    rel["duracao_s"] = round(time.time() - inicio, 1)
    _paths.atomic_write_text(_caminho(), json.dumps(rel, ensure_ascii=False))
    _logger.info("Backtest diário: %d itens em %.0fs", len(itens), rel["duracao_s"])
    return True
