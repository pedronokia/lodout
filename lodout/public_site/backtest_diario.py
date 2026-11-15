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


def _caminho():
    return _paths.DATA_DIR / "backtest_resultado.json"


def ler() -> dict:
    dados = _paths.load_json_record(_caminho(), {})
    return dados if isinstance(dados, dict) else {}


def ligado() -> bool:
    from lodout._ambiente import ambiente
    return (ambiente("BACKTEST_DIARIO") or "").strip().lower() in ("1", "true", "sim")


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


def rodar_se_preciso() -> bool:
    """Roda no máximo 1x por dia. True se rodou."""
    if time.time() - float(ler().get("ts") or 0) < INTERVALO_S:
        return False
    inicio = time.time()
    itens = montar_itens()
    if not itens:
        return False
    rel = score_backtest.relatorio(itens)
    rel["ts"] = time.time()
    rel["duracao_s"] = round(time.time() - inicio, 1)
    _paths.atomic_write_text(_caminho(), json.dumps(rel, ensure_ascii=False))
    _logger.info("Backtest diário: %d itens em %.0fs", len(itens), rel["duracao_s"])
    return True
