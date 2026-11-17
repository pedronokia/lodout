"""Comprar por encomenda (pedido do usuário, 16/11).

Na Steam dá para comprar por encomenda: você diz quanto paga e espera
alguém vender por esse preço. Demora mais, mas o preço é você quem
escolhe. Aqui o site mostra:

- "encomende por até R$ X": o máximo a pagar para lucrar a meta da
  pessoa (20% sem login) revendendo pelo preço de hoje, já com a taxa
  (`portfolio.max_buy_price`). É conta com o preço de hoje, não previsão;
- a maior encomenda que já existe na Steam (coletada da listing page,
  `scan_engine._encomenda`), porque pedidos maiores são atendidos antes.
"""
from __future__ import annotations

from flask import g, session

from lodout import portfolio
from lodout.public_site import fmt

META_PADRAO = 20


def meta_do_visitante() -> int:
    """A meta de lucro da conta, ou 20% para quem não entrou. Lida uma vez
    por página (a home chama para cada cartão)."""
    if "meta_encomenda" in g:
        return g.meta_encomenda
    meta = META_PADRAO
    steamid = session.get("steamid")
    if steamid:
        from lodout.public_site import account
        try:
            meta = int(account._meta_lucro(steamid))
        except Exception:
            meta = META_PADRAO
    g.meta_encomenda = meta
    return meta


def para_template(preco_hoje, dado_scan=None) -> "dict | None":
    """Atalho dos templates (cartões da home): `encomenda_info(preço)`."""
    return info(preco_hoje, dado_scan, meta_do_visitante())


def info(preco_hoje: "float | None", dado_scan: "dict | None", meta: int) -> "dict | None":
    """Textos do bloco "Comprar por encomenda". None sem preço de hoje."""
    if not isinstance(preco_hoje, (int, float)) or preco_hoje <= 0:
        return None
    ate = round(portfolio.max_buy_price(float(preco_hoje), meta), 2)
    maior = (dado_scan or {}).get("maior")
    pedidos = (dado_scan or {}).get("pedidos")
    if isinstance(maior, (int, float)) and maior > 0:
        situacao = ("acima" if ate > maior + 0.005 else
                    "igual" if abs(ate - maior) <= 0.005 else "abaixo")
    else:
        maior, situacao = None, None
    return {
        "ate": ate,
        "ate_fmt": fmt.brl(ate),
        "meta": meta,
        "maior_fmt": fmt.brl(maior) if maior else None,
        "pedidos": pedidos if isinstance(pedidos, int) else None,
        "situacao": situacao,
    }


def sugestao(preco_hoje: "float | None", dado_scan: "dict | None") -> "dict | None":
    """Encomenda sugerida no Ranking (escolha do usuário, 17/11): R$ 0,01
    acima da maior encomenda que já existe, para ficar na frente da fila
    (as maiores são atendidas primeiro). A pessoa só copia; mudar o valor
    fica a critério dela. Não é previsão de lucro: com a taxa da Steam,
    revender pelo preço de hoje costuma dar prejuízo, então o site mostra
    só quanto a sugestão fica abaixo do preço de hoje.

    None sem preço de hoje, sem dado da fila, ou quando a frente da fila
    já chega ao preço de hoje (aí comprar direto sai igual ou mais barato)."""
    if not isinstance(preco_hoje, (int, float)) or preco_hoje <= 0:
        return None
    maior = (dado_scan or {}).get("maior")
    if not isinstance(maior, (int, float)) or maior <= 0:
        return None
    valor = round(float(maior) + 0.01, 2)
    if valor >= float(preco_hoje):
        return None
    pedidos = (dado_scan or {}).get("pedidos")
    return {
        "valor": valor,
        "valor_fmt": fmt.brl(valor),
        "copiar": f"{valor:.2f}".replace(".", ","),
        "abaixo_pct": max(1, int(round(100 * (1 - valor / float(preco_hoje))))),
        "maior_fmt": fmt.brl(float(maior)),
        "pedidos": int(pedidos) if isinstance(pedidos, (int, float)) else None,
    }
