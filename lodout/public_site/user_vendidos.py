"""Itens que a pessoa marcou como vendidos na conta (pedido do usuário,
16/11). Ficam na página Histórico, com quanto pagou, por quanto vendeu e
o lucro já sem a taxa da Steam -- separados de "Meus trades" (as trocas).

A Steam não mostra vendas nem trocas publicamente (só com login ou chave
de API, que o site nunca pede): a venda é marcada pela própria pessoa.
"""
from __future__ import annotations

from pathlib import Path

from lodout import trades as trades_mod
from lodout.public_site import user_store

_KIND = "vendidos"


def load(steamid: str, path: "Path | str | None" = None) -> list[dict]:
    dados = user_store.load_user_json(steamid, _KIND, [], path=path)
    return dados if isinstance(dados, list) else []


# Campos do lote guardados com a venda, para "Desfazer venda" devolver o
# item como estava (revisão 16/11, rodada 2).
_CAMPOS_LOTE = ("lote", "source", "added_ts", "fora_desde", "anunciado", "anuncio_preco")


def adicionar(steamid: str, name: str, custo: float, preco_venda: float,
              quantidade: int, path: "Path | str | None" = None,
              posicao: "dict | None" = None) -> dict:
    """Registra a venda. `preco_venda` é o que o comprador pagou (por
    unidade); o líquido desconta a taxa, como no resto do site.
    `posicao` é o lote de onde saiu (para desfazer)."""
    venda = trades_mod.build_trade(name, custo, preco_venda, quantidade,
                                   source="conta")
    if posicao:
        venda["posicao"] = {k: posicao[k] for k in _CAMPOS_LOTE if posicao.get(k) is not None}
    registros = load(steamid, path=path)
    registros.append(venda)
    user_store.save_user_json(steamid, _KIND, registros, path=path)
    return venda


def remover(steamid: str, index: int, path: "Path | str | None" = None) -> "dict | None":
    registros = load(steamid, path=path)
    if not (0 <= index < len(registros)):
        return None
    tirado = registros.pop(index)
    user_store.save_user_json(steamid, _KIND, registros, path=path)
    return tirado


def posicao_de_volta(venda: dict, agora: float) -> dict:
    """O lote que volta para a conta ao desfazer a venda: com o valor pago
    e marcado como fora do inventário (se o item estiver no inventário, a
    próxima sincronização tira a marca)."""
    antes = venda.get("posicao") if isinstance(venda.get("posicao"), dict) else {}
    pos = {k: antes[k] for k in _CAMPOS_LOTE if antes.get(k) is not None}
    pos.update({"name": venda.get("name"), "cost": venda.get("buy_cost"),
                "quantity": int(venda.get("quantity") or 1)})
    pos.setdefault("source", "steam")
    pos.setdefault("added_ts", agora)
    pos.setdefault("fora_desde", agora)
    return pos
