"""Itens a mais com nota, escolhidos do catálogo (2026-11-16).

Hoje a coleta completa (worker) dá nota aos ~180 itens de
`scan_targets` (sem adesivos). Cada item a mais custa ~12 s por coleta
(~50 s por dia, 4 coletas) e esse tempo sai da varredura do catálogo,
que divide o mesmo limite da Steam. Plano aprovado: subir em degraus de
+100, olhando os bloqueios (`/api/health` -> ultimo_ciclo_worker.
pausas_429) antes de cada degrau. Acima de ~500 a volta do catálogo
passa de 1,5 dia: não subir além disso.

Quem entra: os itens mais anunciados do catálogo (mais gente vendendo
= histórico mais denso = nota mais confiável) nas categorias que o site
já mostra com nota, a partir de R$ 1 (cotação do catálogo), sem os que
já estão na coleta. A lista é refeita no máximo 1x por dia e mantém quem
já estava enquanto seguir entre os mais anunciados, para a nota de cada
item ter continuidade.

`LODOUT_ITENS_EXTRAS` (0 a 400) muda a quantidade; 0 desliga.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from lodout import _paths
from lodout._ambiente import ambiente
from lodout.public_site import catalogo

_logger = logging.getLogger(__name__)

QUANTIDADE_PADRAO = 100
_QUANTIDADE_MAX = 400
_RENOVA_S = 24 * 3600
_PRECO_MIN_BRL = 1.0
# Muda quando o jeito de escolher muda: a lista salva é refeita na hora,
# sem esperar as 24 h (2: piso de preço antes do corte, 16/11).
_CRITERIO = 2
# As mesmas abas da coleta (`scan_targets`, sem adesivos). Escopetas e
# metralhadoras ficam de fora: virariam abas novas na home.
_CATEGORIAS = ("Rifles", "Pistolas", "Facas", "Luvas", "SMGs", "Caixas",
               "Cápsulas", "Cápsulas de autógrafo")


def quantidade() -> int:
    try:
        n = int(ambiente("ITENS_EXTRAS", str(QUANTIDADE_PADRAO)))
    except (TypeError, ValueError):
        n = QUANTIDADE_PADRAO
    return max(0, min(_QUANTIDADE_MAX, n))


def _caminho() -> Path:
    return Path(_paths.DATA_DIR) / "itens_extras.json"


def ler() -> dict:
    dados = _paths.load_json_record(_caminho(), {})
    return dados if isinstance(dados, dict) else {}


def _candidatos(ja: "set[str]", limite: int) -> "list[tuple[str, str]]":
    """(nome, categoria) dos mais anunciados, sem os que já estão na
    coleta e sem os baratos demais."""
    conn = catalogo._conectar_leitura()
    if conn is None:
        return []
    taxa = catalogo.cambio()
    marcas = ",".join("?" for _ in _CATEGORIAS)
    # O piso de preço vai no SQL, antes do LIMIT: os mais anunciados do
    # mercado são quase todos skins de centavos, e filtrar depois do corte
    # deixou só 46 dos 100 no primeiro ciclo (16/11). O banco guarda dólar
    # (AGENTS.md): o piso em reais vira dólar. Sem cotação, sem piso.
    piso = " AND preco >= ?" if taxa else ""
    args = (*_CATEGORIAS, *((_PRECO_MIN_BRL / taxa,) if taxa else ()),
            limite + len(ja))
    try:
        linhas = conn.execute(
            f"SELECT nome, categoria FROM itens WHERE categoria IN ({marcas})"
            f" AND a_venda > 0{piso} ORDER BY a_venda DESC, nome LIMIT ?",
            args).fetchall()
    finally:
        conn.close()
    return [(nome, categoria) for nome, categoria in linhas if nome not in ja]


def alvos(ja: "set[str]", agora: "float | None" = None) -> "dict[str, list[str]]":
    """{categoria: [nomes]} a somar aos alvos da coleta. Vazio se
    desligado ou sem catálogo."""
    n = quantidade()
    if n <= 0 or not catalogo.tem_dados():
        return {}
    agora = time.time() if agora is None else agora
    salvo = ler()
    itens = salvo.get("itens") if isinstance(salvo.get("itens"), list) else []
    fresco = (agora - float(salvo.get("ts") or 0) < _RENOVA_S
              and salvo.get("quantidade") == n
              and salvo.get("criterio") == _CRITERIO)
    if not fresco:
        try:
            top = _candidatos(ja, 2 * n)
        except Exception:
            _logger.warning("itens extras: catálogo ilegível", exc_info=True)
            top = []
        if top:
            na_frente = {nome for nome, _ in top}
            # Quem já estava fica, se ainda estiver entre os 2n mais
            # anunciados; o resto completa com os primeiros da lista.
            mantidos = [i for i in itens
                        if isinstance(i, dict) and i.get("nome") in na_frente]
            nomes = {i["nome"] for i in mantidos}
            for nome, categoria in top:
                if len(mantidos) >= n:
                    break
                if nome not in nomes:
                    mantidos.append({"nome": nome, "categoria": categoria})
                    nomes.add(nome)
            itens = mantidos[:n]
            _paths.atomic_write_text(_caminho(), json.dumps(
                {"ts": agora, "quantidade": n, "criterio": _CRITERIO,
                 "itens": itens}, ensure_ascii=False))
    out: "dict[str, list[str]]" = {}
    for i in itens:
        if not isinstance(i, dict) or i.get("nome") in ja:
            continue
        out.setdefault(i.get("categoria") or "Rifles", []).append(i["nome"])
    return out
