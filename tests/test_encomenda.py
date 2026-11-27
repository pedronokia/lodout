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


def test_info_situacao_igual_e_preco_invalido():
    # Para R$ 100 e meta 20%, ate = 72.46
    i = encomenda.info(100.0, {"maior": 72.46, "pedidos": "invalido"}, 20)
    assert i["situacao"] == "igual"
    assert i["pedidos"] is None
    assert encomenda.info(0, {"maior": 10.0}, 20) is None
    assert encomenda.info(-5.0, {"maior": 10.0}, 20) is None


def test_sugestao_calcula_frente_da_fila_e_filtra_casos_invalidos():
    s = encomenda.sugestao(100.0, {"maior": 75.50, "pedidos": 1234})
    assert s["valor"] == 75.51
    assert s["valor_fmt"] == "R$ 75,51"
    assert s["copiar"] == "75,51"
    assert s["abaixo_pct"] == 24
    assert s["maior_fmt"] == "R$ 75,50"
    assert s["pedidos"] == 1234

    # Pedidos ausente/inválido vira None; margem muito pequena mantém mínimo 1%.
    s2 = encomenda.sugestao(100.0, {"maior": 99.80, "pedidos": None})
    assert s2["valor"] == 99.81 and s2["abaixo_pct"] == 1 and s2["pedidos"] is None

    # Sem preço, sem fila, fila <= 0 ou frente da fila >= preço de hoje -> None.
    assert encomenda.sugestao(None, {"maior": 10.0}) is None
    assert encomenda.sugestao(0, {"maior": 10.0}) is None
    assert encomenda.sugestao(100.0, None) is None
    assert encomenda.sugestao(100.0, {"maior": 0}) is None
    assert encomenda.sugestao(100.0, {"maior": 99.99}) is None
    assert encomenda.sugestao(100.0, {"maior": 120.0}) is None


def test_meta_do_visitante_anonimo_logado_cache_e_fallback(monkeypatch):
    from flask import Flask, g, session
    from lodout.public_site import account

    app = Flask(__name__)
    app.secret_key = "teste"

    # Visitante sem login recebe META_PADRAO e guarda em flask.g.
    with app.test_request_context("/"):
        assert encomenda.meta_do_visitante() == encomenda.META_PADRAO
        assert g.meta_encomenda == encomenda.META_PADRAO
        # Segunda chamada no mesmo request usa o cache de g.
        g.meta_encomenda = 35
        assert encomenda.meta_do_visitante() == 35

    # Visitante logado lê a meta da conta.
    chamadas = []
    monkeypatch.setattr(account, "_meta_lucro", lambda sid: (chamadas.append(sid) or 45))
    with app.test_request_context("/"):
        session["steamid"] = "76561198000000105"
        assert encomenda.meta_do_visitante() == 45
        assert encomenda.meta_do_visitante() == 45
        assert chamadas == ["76561198000000105"]

    # Erro ao ler meta cai no padrão sem quebrar a página.
    monkeypatch.setattr(account, "_meta_lucro", lambda sid: (_ for _ in ()).throw(RuntimeError("db")))
    with app.test_request_context("/"):
        session["steamid"] = "76561198000000105"
        assert encomenda.meta_do_visitante() == encomenda.META_PADRAO
