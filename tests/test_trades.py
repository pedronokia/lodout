"""Testes de `trades.build_trade` -- cálculo de lucro realizado com taxa Steam."""
from __future__ import annotations

import pytest

from lodout import trades


def test_build_trade_pnl_pct_is_0_100():
    """build_trade.pnl_pct retorna 0-100, nao fracao."""
    t = trades.build_trade("AK-47 | Redline", 100.0, 150.0, 1)
    assert t["pnl_pct"] == pytest.approx(30.43, abs=0.01)


def test_build_trade_profit():
    t = trades.build_trade("AK-47 | Redline", 200.0, 350.0, 1)
    assert t["pnl"] == pytest.approx(104.35, abs=0.02)
    assert t["name"] == "AK-47 | Redline"


def test_build_trade_loss():
    t = trades.build_trade("AWP | Asiimov", 700.0, 600.0, 1)
    assert t["pnl"] < 0
    assert t["pnl"] == pytest.approx(-178.26, abs=0.02)


def test_build_trade_multiple_qty():
    t = trades.build_trade("Item", 100.0, 150.0, 3)
    assert t["cost_total"] == 300.0
    assert t["pnl"] == pytest.approx(91.30, abs=0.02)


def test_build_trade_buy_and_sell_ts():
    t = trades.build_trade("A", 100.0, 200.0, 1, buy_ts=1000000, sell_ts=1086400)
    assert t["buy_ts"] == 1000000
    assert t["sell_ts"] == 1086400


def test_build_trade_notes_tags_source():
    t = trades.build_trade(
        "Item", 100.0, 200.0, 1,
        notes="Bom negocio", tags=["profit", "skin"],
        source="manual", steam_event_id="ev-1",
    )
    assert t["notes"] == "Bom negocio"
    assert t["tags"] == ["profit", "skin"]
    assert t["source"] == "manual"
    assert t["steam_event_id"] == "ev-1"
