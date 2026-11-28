"""Preco-alvo de venda e preco maximo de compra.

O modelo de taxa aqui e' o do `portfolio`, que e' o correto pra Steam: a
taxa incide sobre o valor do VENDEDOR, nao sobre o preco de compra. Voce
lista a R$ 115, o comprador paga 115, voce recebe 100. Logo o break-even
e' +15%, e nao os +17,65% que o `backtest.breakeven_gross` devolve (esse
usa preco*(1-taxa), que e' outro modelo).
"""
from __future__ import annotations

import pytest

from lodout import portfolio


# ── o modelo de taxa ───────────────────────────────────────────────

def test_listar_a_115_devolve_100():
    assert portfolio.net_proceeds(115.0) == pytest.approx(100.0)


def test_break_even_e_15_por_cento():
    assert portfolio.break_even_price(100.0) == pytest.approx(115.0)


# ── max_buy_price ──────────────────────────────────────────────────

def test_maximo_de_compra_sem_margem_e_o_ponto_de_indiferenca():
    """Vendendo a 115 voce recebe 100; pagar mais que 100 da' prejuizo."""
    assert portfolio.max_buy_price(115.0) == pytest.approx(100.0, abs=0.01)


def test_maximo_de_compra_com_margem():
    """Pra sobrar 20% vendendo a 115, o teto de compra cai."""
    teto = portfolio.max_buy_price(115.0, margin_pct=20.0)
    assert teto == pytest.approx(100.0 / 1.2, abs=0.01)
    # e a conta fecha: comprando no teto, o lucro e' os 20%
    lucro = portfolio.net_proceeds(115.0) - teto
    assert lucro / teto * 100 == pytest.approx(20.0, abs=0.1)


def test_maximo_de_compra_cresce_com_o_preco_de_venda():
    assert portfolio.max_buy_price(200.0) > portfolio.max_buy_price(100.0)
