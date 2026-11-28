from __future__ import annotations

import time

from lodout.portfolio import net_proceeds


def build_trade(name: str, buy_cost: float, sell_price: float,
                quantity: int = 1,
                notes: str = "", tags: list[str] | None = None,
                buy_ts: float | None = None,
                source: str = "manual",
                steam_event_id: str | None = None,
                sell_ts: float | None = None) -> dict:
    """Monta o registro de venda/trade já com taxa da Steam descontada."""
    cost_total = buy_cost * quantity
    net = net_proceeds(sell_price) * quantity
    pnl = net - cost_total
    now = time.time()
    return {
        "name": name,
        "buy_cost": buy_cost,
        "sell_price": sell_price,
        "quantity": quantity,
        "cost_total": cost_total,
        "net_received": round(net, 2),
        "pnl": round(pnl, 2),
        "pnl_pct": round((pnl / cost_total * 100) if cost_total else 0, 2),
        "buy_ts": buy_ts or now,
        "sell_ts": sell_ts or now,
        "notes": notes,
        "tags": tags or [],
        "source": source,
        "steam_event_id": steam_event_id,
    }
