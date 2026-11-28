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
    nome -- cada adição é uma linha própria com `lote` próprio)."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        lista.append({
            "name": name,
            "cost": cost,
            "quantity": quantity,
            "added_ts": time.time(),
            "source": "manual",
            "lote": novo_lote(),
        })
        return True, lista, lista

    _, result = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return result


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


def update_position_cost(steamid: str, name: str, cost: "float | None",
                         path: "Path | str | None" = None,
                         lote: "str | None" = None) -> "list[dict] | None":
    """Atualiza o custo das posições com esse nome (só do `lote`, se
    dado). None se nenhuma posição bater (nada pra atualizar)."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        found = False
        for pos in lista:
            if _alvo(pos, name, lote):
                pos["cost"] = cost
                found = True
        if not found:
            return False, lista, None
        return True, lista, lista

    _, result = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return result


def _fora_alvo(pos: dict, name: str, lote: "str | None") -> bool:
    """Lote fora do inventário que a pessoa marcou (sem `lote`, só os
    marcados fora desse nome -- nunca os que ainda estão no inventário)."""
    return _alvo(pos, name, lote) and bool(pos.get("fora_desde"))


def marcar_anunciado(steamid: str, name: str, anunciado: bool,
                     lote: "str | None" = None,
                     path: "Path | str | None" = None,
                     preco: "float | None" = None) -> bool:
    """Item fora do inventário: a pessoa diz que está anunciado no Mercado
    (ou desmarca), e por quanto (`anuncio_preco`, o que o comprador paga
    por unidade; o "Vendi" já vem com ele). True se algo mudou (16/11)."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        mudou = False
        for pos in lista:
            if not _fora_alvo(pos, name, lote):
                continue
            antes = (bool(pos.get("anunciado")), pos.get("anuncio_preco"))
            if anunciado:
                pos["anunciado"] = True
                if preco is not None:
                    pos["anuncio_preco"] = round(float(preco), 2)
            else:
                pos.pop("anunciado", None)
                pos.pop("anuncio_preco", None)
            mudou = mudou or antes != (bool(pos.get("anunciado")), pos.get("anuncio_preco"))
        return mudou, lista, mudou

    _, mudou = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return bool(mudou)


def tirar_vendidas(steamid: str, name: str, quantidade: int,
                   lote: "str | None" = None,
                   path: "Path | str | None" = None) -> "dict | None":
    """Tira `quantidade` unidades de um lote fora do inventário que a
    pessoa vendeu. Devolve o lote como estava (para registrar a venda) ou
    None se não achou, se o lote não tem valor pago ou se a quantidade
    não cabe."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        for i, pos in enumerate(lista):
            if not _fora_alvo(pos, name, lote):
                continue
            qtd = int(pos.get("quantity") or 1)
            if pos.get("cost") is None or not 1 <= quantidade <= qtd:
                continue
            antes = dict(pos)
            if quantidade == qtd:
                lista.pop(i)
            else:
                pos["quantity"] = qtd - quantidade
            return True, lista, antes
        return False, lista, None

    _, antes = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return antes


def devolver_lote(steamid: str, pos: dict,
                  path: "Path | str | None" = None) -> None:
    """Põe de volta um lote tirado por "Vendi" (desfazer a venda). Se o
    lote de onde saiu ainda existe (venda de parte das unidades), soma as
    unidades nele; senão, volta como lote próprio com ID único."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        lote = pos.get("lote")
        alvo = dict(pos)
        for atual in lista:
            if lote and atual.get("lote") == lote:
                if (atual.get("name") == alvo.get("name")
                        and atual.get("cost") == alvo.get("cost")
                        and atual.get("fora_desde")):
                    atual["quantity"] = (
                        int(atual.get("quantity") or 1) + int(alvo.get("quantity") or 1)
                    )
                    return True, lista, None
                alvo["lote"] = novo_lote()
                break
        if not alvo.get("lote"):
            alvo["lote"] = novo_lote()
        lista.append(alvo)
        return True, lista, None

    user_store.update_user_json(steamid, _KIND, list, _mut, path=path)


def remove_position(steamid: str, name: str,
                    path: "Path | str | None" = None,
                    lote: "str | None" = None) -> bool:
    """Remove as posições com esse nome (só o `lote`, se dado). True se
    algo foi removido."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        remaining = [p for p in lista if not _alvo(p, name, lote)]
        changed = len(remaining) != len(lista)
        return changed, remaining, changed

    _, changed = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return bool(changed)


def separar(steamid: str, name: str, quantidade: int,
            lote: "str | None" = None,
            path: "Path | str | None" = None) -> "str | None":
    """Tira `quantidade` unidades de uma posição no inventário e cria um
    lote novo, sem valor pago, logo depois dela -- pra quem pagou valores
    diferentes pelo mesmo item (pedido do usuário, 2026-11-15). Devolve o
    id do lote novo, ou None se não der (posição não achada ou quantidade
    fora de 1..unidades-1)."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        for i, pos in enumerate(lista):
            if not _alvo(pos, name, lote) or pos.get("fora_desde"):
                continue
            qtd = int(pos.get("quantity") or 1)
            if not 1 <= quantidade < qtd:
                continue
            pos["quantity"] = qtd - quantidade
            pos.setdefault("lote", novo_lote())
            novo = {**pos, "quantity": quantidade, "cost": None,
                    "added_ts": time.time(), "lote": novo_lote()}
            lista.insert(i + 1, novo)
            return True, lista, novo["lote"]
        return False, lista, None

    _, novo_id = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return novo_id


def juntar(steamid: str, name: str,
           path: "Path | str | None" = None) -> str:
    """Junta os lotes de um item numa posição só, com o valor médio
    ponderado pelas unidades (sem misturar itens do inventário Steam com
    linhas adicionadas à mão). Devolve "ok", "nada" (menos de 2 lotes) ou
    "misto" (algum lote com valor e outro sem: juntar inventaria um
    preço, então não junta)."""
    def _mut(positions):
        lista = list(positions) if isinstance(positions, list) else []
        # Lotes fora do inventário (anunciados ou vendidos) ficam como estão:
        # juntar com eles misturaria o que a pessoa ainda tem com o que talvez
        # já tenha vendido (revisão 16/11). Também não mistura origem steam/manual.
        candidatos = [p for p in lista if p.get("name") == name and not p.get("fora_desde")]
        steam_lotes = [p for p in candidatos if p.get("source") == "steam"]
        manuais = [p for p in candidatos if p.get("source") != "steam"]
        lotes = steam_lotes if len(steam_lotes) >= 2 else (manuais if len(manuais) >= 2 else [])
        if len(lotes) < 2:
            return False, lista, "nada"
        com_valor = [p for p in lotes if p.get("cost") is not None]
        if com_valor and len(com_valor) != len(lotes):
            return False, lista, "misto"
        unidades = sum(int(p.get("quantity") or 1) for p in lotes)
        custo = (round(sum(float(p["cost"]) * int(p.get("quantity") or 1)
                           for p in lotes) / unidades, 2)
                 if com_valor else None)
        primeiro = lista.index(lotes[0])
        unido = {**lotes[0], "quantity": unidades, "cost": custo}
        unido.pop("lote", None)
        restantes = [p for p in lista if not any(p is l for l in lotes)]
        restantes.insert(min(primeiro, len(restantes)), unido)
        return True, restantes, "ok"

    _, status = user_store.update_user_json(steamid, _KIND, list, _mut, path=path)
    return status
