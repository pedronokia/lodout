"""Trocas entre jogadores ("Meus trades", pedido do usuário 17/11).

Antes, "Meus trades" registrava compra e venda encerradas -- o mesmo que
"Vendi" já leva para "Itens vendidos". Para o usuário, trade é TROCA: o
que ele deu, o que recebeu e quanto valia cada lado no dia. Troca direta
entre jogadores não paga a taxa da Steam, então o saldo é só a diferença
de valor de mercado.

Registro: {"ts", "deu": [{name, quantity, valor}], "recebeu": [...],
"notas"}; `valor` é o preço de mercado de UMA unidade no dia (a pessoa
digita; o formulário sugere o preço de hoje).

Os registros antigos de compra e venda (kind "trades") vão para
`user_vendidos` na primeira vez que a pessoa abre "Meus trades" ou o
Histórico (`migrar_trades_antigos`), marcados com source "trades".
"""
from __future__ import annotations

import time
from pathlib import Path

from lodout.public_site import user_store, user_vendidos

_KIND = "trocas"
_KIND_ANTIGO = "trades"
MAX_ITENS_POR_LADO = 10


def load(steamid: str, path: "Path | str | None" = None) -> list[dict]:
    dados = user_store.load_user_json(steamid, _KIND, [], path=path)
    return dados if isinstance(dados, list) else []


def total(lado: "list[dict]") -> float:
    return round(sum(int(i.get("quantity") or 1) * float(i.get("valor") or 0)
                     for i in lado or []), 2)


def adicionar(steamid: str, deu: "list[dict]", recebeu: "list[dict]",
              notas: str = "", ts: "float | None" = None,
              path: "Path | str | None" = None) -> dict:
    """Registra uma troca. Cada lado: [{name, quantity, valor}], já
    validado por quem chama (rota)."""
    troca = {
        "ts": time.time() if ts is None else ts,
        "deu": [dict(i) for i in deu][:MAX_ITENS_POR_LADO],
        "recebeu": [dict(i) for i in recebeu][:MAX_ITENS_POR_LADO],
        "notas": (notas or "")[:300],
    }
    registros = load(steamid, path=path)
    registros.append(troca)
    user_store.save_user_json(steamid, _KIND, registros, path=path)
    return troca


def remover(steamid: str, index: int, path: "Path | str | None" = None) -> "dict | None":
    registros = load(steamid, path=path)
    if not (0 <= index < len(registros)):
        return None
    tirado = registros.pop(index)
    user_store.save_user_json(steamid, _KIND, registros, path=path)
    return tirado


def migrar_trades_antigos(steamid: str, path: "Path | str | None" = None) -> int:
    """Leva os registros antigos de compra e venda ("Meus trades" até
    17/11) para "Itens vendidos". Devolve quantos foram movidos (0 se não
    havia nada). Idempotente: depois de mover, o kind antigo fica vazio."""
    antigos = user_store.load_user_json(steamid, _KIND_ANTIGO, [], path=path)
    if not isinstance(antigos, list) or not antigos:
        return 0
    vendidos = user_vendidos.load(steamid, path=path)
    movidos = 0
    for t in antigos:
        if isinstance(t, dict) and t.get("name") and t.get("sell_price") is not None:
            vendidos.append({**t, "source": "trades"})
            movidos += 1
    user_store.save_user_json(steamid, user_vendidos._KIND, vendidos, path=path)
    user_store.save_user_json(steamid, _KIND_ANTIGO, [], path=path)
    return movidos
