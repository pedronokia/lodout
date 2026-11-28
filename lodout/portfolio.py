"""Cálculos fee-aware de portfólio -- quanto paguei / quanto devo vender.

O pulo do gato é a taxa de ~15% do Steam. Você lista por P, mas recebe ~P/1.15.
Logo, 'vale mais do que paguei' NÃO é lucro -- só é lucro DEPOIS da taxa. Este
módulo concentra essas contas puras (a persistência por conta fica em
`lodout.public_site.user_portfolio`). Obs: o 'lucro' aqui é em saldo Steam (a
Wallet não saca pra conta) -- a ferramenta é pra quem opera dentro do Steam.
"""
from __future__ import annotations

# ~5% Steam + 10% jogo, cobrados sobre o valor que o VENDEDOR recebe.
STEAM_FEE = 0.15


def net_proceeds(price: float, fee_rate: float = STEAM_FEE) -> float:
    """Quanto VOCE recebe ao vender por `price` (liquido da taxa).
    Steam: buyer_price = seller_amount * (1+fee) => seller = price/(1+fee)."""
    return price / (1.0 + fee_rate)


def break_even_price(cost: float, fee_rate: float = STEAM_FEE) -> float:
    """Preco de LISTAGEM necessario pra receber de volta o que custou."""
    return cost * (1.0 + fee_rate)


def max_buy_price(sell_price: float, margin_pct: float = 0.0,
                  fee_rate: float = STEAM_FEE) -> float:
    """Maximo a pagar hoje pra, vendendo por `sell_price`, sobrar a margem.

    Responde a pergunta do Scanner: "vale a pena comprar por quanto?".
    Com margem 0 devolve o preco de indiferenca -- pagar mais que isso da'
    prejuizo mesmo que a venda saia no preco previsto.
    """
    liquido = net_proceeds(sell_price, fee_rate)
    return liquido / (1.0 + margin_pct / 100.0)


def position_pnl(cost: float, current_price: float, quantity: int = 1,
                 fee_rate: float = STEAM_FEE) -> dict:
    """Breakdown honesto de UMA posicao. 'market' e' o bruto (o que aparenta
    valer); 'net_if_sold' e' o que voce realmente recebe; 'pnl' e' a verdade."""
    cost_total = cost * quantity
    market = current_price * quantity
    net = net_proceeds(current_price, fee_rate) * quantity
    pnl = net - cost_total
    if pnl > 0.005:
        status = "profit"
    elif pnl < -0.005:
        status = "loss"
    else:
        status = "even"
    return {
        "cost_total": cost_total,
        "market": market,
        "net_if_sold": net,
        "pnl": pnl,
        "pnl_pct": (pnl / cost_total * 100) if cost_total else 0.0,
        "break_even": break_even_price(cost, fee_rate),
        "status": status,
    }


def has_cost_basis(pos: dict) -> bool:
    """True se a posicao tem custo CONHECIDO.

    O sync grava `cost: 0.0` porque a Steam nao diz quanto voce pagou --
    isso e' "desconhecido", nao "custou zero". Tratar os dois igual faz o
    P&L reportar o inventario inteiro como lucro: foi o que aconteceu na
    tela de conta (R$ 850,42 de "lucro" com R$ 0,00 investido).

    Item de drop realmente custou zero, mas ai' e' entrada manual --
    por isso a distincao olha a origem, nao so' o valor.
    """
    cost = pos.get("cost")
    if cost is None:
        return False
    try:
        cost = float(cost)
    except (TypeError, ValueError):
        return False
    if cost > 0:
        return True
    return pos.get("source") != "steam_sync"


def evaluate_portfolio(positions: list[dict], price_fn,
                       fee_rate: float = STEAM_FEE) -> dict:
    """positions: [{name, cost, quantity}]. price_fn(name) -> float | None.
    Retorna {rows, totals}. price_fn None -> linha sem preco (item ilustravel).

    P&L so' agrega posicoes com custo conhecido (ver has_cost_basis). Valor
    de mercado e liquido agregam TUDO -- esses nao dependem de custo.
    `totals.unknown_cost` diz quantas ficaram de fora, pra UI poder avisar
    em vez de exibir lucro inventado.

    Dois totais de custo, porque respondem perguntas diferentes:

    - `cost_known` -- tudo que o dono declarou ter pago, tenha o item
      cotacao ou nao. E' o "Total investido" da tela.
    - `cost` -- so' o custo das posicoes que entraram no P&L. Fica de par
      com `pnl`/`pnl_pct`; misturar as duas daria uma porcentagem sobre um
      custo cujo retorno nao foi medido.

    Sao iguais quando toda posicao tem preco, e divergem exatamente quando
    a Steam nao respondeu.
    """
    rows: list[dict] = []
    t_cost = t_market = t_net = 0.0
    t_cost_known = 0.0
    t_net_conhecido = 0.0
    sem_custo = 0
    com_custo = 0
    # Por item (nome), não por linha: separar um item em lotes ("valores
    # diferentes?") não pode mudar "N itens" nos cartões (revisão 16/11).
    nomes: set = set()
    nomes_sem_custo: set = set()
    nomes_no_lucro: set = set()
    for pos in positions:
        name = pos["name"]
        nomes.add(name)
        conhecido = has_cost_basis(pos)
        cost = float(pos.get("cost") or 0.0)
        qty = int(pos.get("quantity", 1))
        # Ter custo e' fato da POSICAO, nao da cotacao. Contabilizar isso
        # so' no ramo com preco fazia o lote inteiro sem preco (Steam em
        # 429) reportar `unknown_cost: 0` e "Total investido R$ 0,00" pra
        # quem tinha R$ 850,00 declarados -- o mesmo erro de tratar
        # "desconhecido" e "zero" como a mesma coisa, do avesso.
        if conhecido:
            t_cost_known += cost * qty
        else:
            sem_custo += 1
            nomes_sem_custo.add(name)
        price = price_fn(name)
        icon = pos.get("icon")
        if price is None:
            rows.append({"name": name, "cost": cost, "quantity": qty,
                         "price": None, "pnl": None,
                         "cost_total": cost * qty,
                         "has_cost": conhecido, "icon": icon})
            continue
        d = position_pnl(cost, price, qty, fee_rate)
        if not conhecido:
            # Sem custo nao ha' lucro nem prejuizo -- ha' valor.
            d["pnl"] = None
            d["pnl_pct"] = None
            d["is_profit"] = False
            d["is_loss"] = False
        rows.append({"name": name, "cost": cost, "quantity": qty,
                     "price": price, "has_cost": conhecido, "icon": icon,
                     **d})
        t_market += d["market"]
        t_net += d["net_if_sold"]
        if conhecido:
            com_custo += 1
            nomes_no_lucro.add(name)
            t_cost += d["cost_total"]
            t_net_conhecido += d["net_if_sold"]
    # O gatilho e' EXISTIR posicao com custo conhecido, nao o custo somar
    # mais que zero: drop declarado manualmente custa zero e tem P&L real.
    pnl = (t_net_conhecido - t_cost) if com_custo else None
    totals = {
        "cost": t_cost,
        "cost_known": t_cost_known,
        "market": t_market,
        "net_if_sold": t_net,
        "pnl": pnl,
        "pnl_pct": (pnl / t_cost * 100) if (pnl is not None and t_cost) else None,
        "unknown_cost": sem_custo,
        "known_cost": len(positions) - sem_custo,
        # Quantas entraram no P&L (custo conhecido E preço hoje): menor que
        # known_cost quando algum item com custo está sem preço.
        "pnl_positions": com_custo,
        "positions": len(positions),
        # Contagens por item (lotes do mesmo nome contam uma vez): um item
        # com algum lote sem valor pago conta como "sem valor pago".
        "itens": len(nomes),
        "itens_sem_custo": len(nomes_sem_custo),
        "itens_com_custo": len(nomes - nomes_sem_custo),
        "itens_no_lucro": len(nomes_no_lucro),
    }
    return {"rows": rows, "totals": totals}
