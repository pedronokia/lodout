"""Histórico de valor da carteira (site público) -- por usuário.

Cada ponto contém `{ts, total}` e, desde 16/11, `comp`/`unid` (quais
itens havia, ver `composicao`).
`record_if_changed` pula pontos quando o total é igual ao último; sem isso,
cada visita a `/conta` encheria a série de repetições. O histórico tem limite
de 500 pontos.
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from lodout.public_site import user_store

_KIND = "history"
_CAP = 500


def load_history(steamid: str, path: "Path | str | None" = None) -> list[dict]:
    return user_store.load_user_json(steamid, _KIND, [], path=path)


def composicao(itens: "dict[str, int]") -> dict:
    """Resumo de quais itens havia na conta: `comp` (impressão curta de
    nome x quantidade) e `unid` (unidades). Serve só para saber se itens
    entraram ou saíram entre dois pontos (revisão 16/11: o "+R$ X desde
    ontem" somava a caixa recém-adicionada como se o mercado subisse)."""
    texto = "\n".join(f"{nome}\t{qtd}" for nome, qtd in sorted(itens.items()))
    return {"comp": hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12],
            "unid": int(sum(itens.values()))}


def record_if_changed(steamid: str, total: float,
                      path: "Path | str | None" = None,
                      now: "float | None" = None,
                      itens: "dict[str, int] | None" = None) -> list[dict]:
    """Grava {ts, total[, comp, unid]} se `total` (ou, com `itens`, a
    composição) mudou desde o último ponto.

    Chamado a cada visita a `/conta` -- sem o dedup, cada refresh da
    página adicionaria um ponto idêntico ao anterior.
    """
    series = load_history(steamid, path=path)
    extra = composicao(itens) if itens is not None else {}
    if series and series[-1].get("total") == float(total) and \
            series[-1].get("comp") == extra.get("comp"):
        return series
    series.append({"ts": now if now is not None else time.time(),
                   "total": float(total), **extra})
    series = series[-_CAP:]
    user_store.save_user_json(steamid, _KIND, series, path=path)
    return series
