"""Distância do topo histórico (`signals.relative_to_ath`)."""
from __future__ import annotations

from lodout import signals

DIA = 86400


def _ph(precos):
    return [{"time": i * DIA, "price_median": p, "purchases": 1}
            for i, p in enumerate(precos)]


def test_rotulo_ath_em_reais():
    rta = signals.relative_to_ath(_ph([1.0] * 9 + [12.5, 10.0]))
    assert rta["label"] == "Preço a 80% do ATH (R$ 12,50)"


def test_rel_ath_do_score_ignora_ponto_horario_isolado():
    """O fator rel_ath da nota usa o mesmo topo diario do exit_context:
    uma compra horaria anomala nao pode virar o "maior preco"."""
    ph = [{"time": i * DIA, "price_median": 200.0, "purchases": 500}
          for i in range(200)]
    ph.append({"time": 150 * DIA + 3600, "price_median": 1403.0,
               "purchases": 1})
    rta = signals.relative_to_ath(ph)
    assert rta["ath"] < 210.0
    assert rta["band"] == "at_ath"
