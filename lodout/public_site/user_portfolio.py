"""Portfólio pessoal (site público) -- mutação por usuário.

A matemática (valor, lucro, breakeven) continua em `portfolio.py`:
`evaluate_portfolio(positions, price_fn)` já recebe a lista direto. Os
dados de cada visitante são persistidos separadamente por conta.

Mesma forma de posição que `portfolio.json` já usa: {name, cost, quantity,
added_ts, source}.
"""
from __future__ import annotations

import secrets
import time
from pathlib import Path

from lodout.public_site import user_store

_KIND = "portfolio"


def load_positions(steamid: str,
                   path: "Path | str | None" = None) -> list[dict]:
    return user_store.load_user_json(steamid, _KIND, [], path=path)


def add_position(steamid: str, name: str, cost: "float | None",
                 quantity: int = 1,
                 path: "Path | str | None" = None) -> list[dict]:
    """Adiciona uma posição nova (não funde com uma existente do mesmo
    nome -- cada adição é
    uma linha própria)."""
    positions = load_positions(steamid, path=path)
    positions.append({
        "name": name,
        "cost": cost,
        "quantity": quantity,
        "added_ts": time.time(),
        "source": "manual",
    })
    user_store.save_user_json(steamid, _KIND, positions, path=path)
    return positions


def novo_lote() -> str:
    """Identificador curto de um lote (unidades do mesmo item com o mesmo
    valor pago). Só precisa ser único dentro da conta da pessoa."""
    return secrets.token_hex(4)


def _alvo(pos: dict, name: str, lote: "str | None") -> bool:
    """A posição é a que a pessoa quis mexer? Com `lote`, só aquele lote;
    sem, todas as posições do nome (comportamento de antes dos lotes)."""
    if pos.get("name") != name:
        return False
    return not lote or pos.get("lote") == lote


def update_position_cost(steamid: str, name: str, cost: float,
                         path: "Path | str | None" = None,
                         lote: "str | None" = None) -> "list[dict] | None":
    """Atualiza o custo das posições com esse nome (só do `lote`, se
    dado). None se nenhuma posição bater (nada pra atualizar)."""
    positions = load_positions(steamid, path=path)
    found = False
    for pos in positions:
        if _alvo(pos, name, lote):
            pos["cost"] = cost
            found = True
    if not found:
        return None
    user_store.save_user_json(steamid, _KIND, positions, path=path)
    return positions


def _fora_alvo(pos: dict, name: str, lote: "str | None") -> bool:
    """Lote fora do inventário que a pessoa marcou (sem `lote`, só os
    marcados fora desse nome -- nunca os que ainda estão no inventário)."""
    return _alvo(pos, name, lote) and bool(pos.get("fora_desde"))


def marcar_anunciado(steamid: str, name: str, anunciado: bool,
                     lote: "str | None" = None,
                     path: "Path | str | None" = None) -> bool:
    """Item fora do inventário: a pessoa diz que está anunciado no Mercado
    (ou desmarca). True se algo mudou (revisão 16/11)."""
    positions = load_positions(steamid, path=path)
    mudou = False
    for pos in positions:
        if _fora_alvo(pos, name, lote) and bool(pos.get("anunciado")) != anunciado:
            if anunciado:
                pos["anunciado"] = True
            else:
                pos.pop("anunciado", None)
            mudou = True
    if mudou:
        user_store.save_user_json(steamid, _KIND, positions, path=path)
    return mudou


def tirar_vendidas(steamid: str, name: str, quantidade: int,
                   lote: "str | None" = None,
                   path: "Path | str | None" = None) -> "dict | None":
    """Tira `quantidade` unidades de um lote fora do inventário que a
    pessoa vendeu. Devolve o lote como estava (para registrar a venda) ou
    None se não achou, se o lote não tem valor pago ou se a quantidade
    não cabe."""
    positions = load_positions(steamid, path=path)
    for i, pos in enumerate(positions):
        if not _fora_alvo(pos, name, lote):
            continue
        qtd = int(pos.get("quantity") or 1)
        if pos.get("cost") is None or not 1 <= quantidade <= qtd:
            return None
        antes = dict(pos)
        if quantidade == qtd:
            positions.pop(i)
        else:
            pos["quantity"] = qtd - quantidade
        user_store.save_user_json(steamid, _KIND, positions, path=path)
        return antes
    return None


def remove_position(steamid: str, name: str,
                    path: "Path | str | None" = None,
                    lote: "str | None" = None) -> bool:
    """Remove as posições com esse nome (só o `lote`, se dado). True se
    algo foi removido."""
    positions = load_positions(steamid, path=path)
    remaining = [p for p in positions if not _alvo(p, name, lote)]
    changed = len(remaining) != len(positions)
    if changed:
        user_store.save_user_json(steamid, _KIND, remaining, path=path)
    return changed


def separar(steamid: str, name: str, quantidade: int,
            lote: "str | None" = None,
            path: "Path | str | None" = None) -> "str | None":
    """Tira `quantidade` unidades de uma posição e cria um lote novo, sem
    valor pago, logo depois dela -- pra quem pagou valores diferentes
    pelo mesmo item (pedido do usuário, 2026-11-15). Devolve o id do
    lote novo, ou None se não der (posição não achada ou quantidade
    fora de 1..unidades-1)."""
    positions = load_positions(steamid, path=path)
    for i, pos in enumerate(positions):
        if not _alvo(pos, name, lote):
            continue
        qtd = int(pos.get("quantity") or 1)
        if not 1 <= quantidade < qtd:
            return None
        pos["quantity"] = qtd - quantidade
        pos.setdefault("lote", novo_lote())
        novo = {**pos, "quantity": quantidade, "cost": None,
                "added_ts": time.time(), "lote": novo_lote()}
        positions.insert(i + 1, novo)
        user_store.save_user_json(steamid, _KIND, positions, path=path)
        return novo["lote"]
    return None


def juntar(steamid: str, name: str,
           path: "Path | str | None" = None) -> str:
    """Junta os lotes de um item numa posição só, com o valor médio
    ponderado pelas unidades. Devolve "ok", "nada" (menos de 2 lotes) ou
    "misto" (algum lote com valor e outro sem: juntar inventaria um
    preço, então não junta)."""
    positions = load_positions(steamid, path=path)
    # Lotes fora do inventário (anunciados ou vendidos) ficam como estão:
    # juntar com eles misturaria o que a pessoa ainda tem com o que talvez
    # já tenha vendido (revisão 16/11).
    lotes = [p for p in positions if p.get("name") == name and not p.get("fora_desde")]
    if len(lotes) < 2:
        return "nada"
    com_valor = [p for p in lotes if p.get("cost") is not None]
    if com_valor and len(com_valor) != len(lotes):
        return "misto"
    unidades = sum(int(p.get("quantity") or 1) for p in lotes)
    custo = (round(sum(float(p["cost"]) * int(p.get("quantity") or 1)
                       for p in lotes) / unidades, 2)
             if com_valor else None)
    primeiro = positions.index(lotes[0])
    unido = {**lotes[0], "quantity": unidades, "cost": custo}
    unido.pop("lote", None)
    restantes = [p for p in positions if not any(p is l for l in lotes)]
    restantes.insert(min(primeiro, len(restantes)), unido)
    user_store.save_user_json(steamid, _KIND, restantes, path=path)
    return "ok"
