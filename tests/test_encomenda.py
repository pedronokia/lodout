"""Comprar por encomenda (pedido do usuário, 16/11)."""
from __future__ import annotations

from lodout import scan_engine
from lodout.public_site import encomenda


def test_conta_da_encomenda():
    # R$ 100 hoje: recebe 86,96 vendendo; para lucrar 20%, paga até 72,46.
    i = encomenda.info(100.0, {"maior": 70.0, "pedidos": 1234}, 20)
    assert i["ate_fmt"] == "R$ 72,46" and i["meta"] == 20
    assert i["maior_fmt"] == "R$ 70,00" and i["pedidos"] == 1234
    assert i["situacao"] == "acima"
    assert encomenda.info(100.0, {"maior": 80.0}, 20)["situacao"] == "abaixo"
    assert encomenda.info(100.0, None, 50)["ate_fmt"] == "R$ 57,97"
    assert encomenda.info(100.0, None, 50)["copiar"] == "57,97"
    assert encomenda.info(None, None, 20) is None


def test_maior_encomenda_da_pagina_em_reais():
    ob = {"best_bid": 7012, "best_ask": 7499, "buy_count": 10268}
    # Com o fator do ciclo (centavos).
    assert scan_engine._encomenda(ob, False, 74.99, 0.01) == {"maior": 70.12, "pedidos": 10268}
    # Sem fator: deduz a potência de 10 pelo menor anúncio.
    assert scan_engine._encomenda(ob, False, 74.90, None) == {"maior": 70.12, "pedidos": 10268}
    # Book de outro desgaste, sem lance ou incoerente: nada.
    assert scan_engine._encomenda(ob, True, 74.99, 0.01) is None
    assert scan_engine._encomenda({"best_ask": 7499}, False, 74.99, 0.01) is None
    assert scan_engine._encomenda({"best_bid": 9000, "best_ask": 7499}, False, 74.99, 0.01) is None
