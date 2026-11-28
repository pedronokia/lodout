"""Testes de regressão das 3 correções de nota (spread, pump_risk 30d e
consistência volume_history/category em enhanced_score)."""
from __future__ import annotations

from datetime import date, timedelta

from lodout import scan_engine, signals, steam_api


def test_fair_value_verdict_spread_zero_e_sem_dupla_contagem_no_denominador():
    # spread == 0 (ask == bid): mercado mais apertado possível -> tight (+25 na nota)
    v0 = steam_api.fair_value_verdict(100.0, 100.0, spread=0)
    assert v0["spread_pct"] == 0.0
    assert v0["spread_verdict"] == "tight"

    # spread = 1100 centavos em lowest = R$ 100 (10000 centavos) -> 11% (wide),
    # antes dava 1100 / 11100 = 9.91% ("normal") por somar spread no denominador.
    v11 = steam_api.fair_value_verdict(100.0, 100.0, spread=1100)
    assert v11["spread_pct"] == 11.0
    assert v11["spread_verdict"] == "wide"


def test_fair_value_verdict_usa_best_ask_do_proprio_book_em_variantes_irmas():
    # Book de Minimal Wear (best_ask=100000, spread=1500 = 1.5% tight) emprestado
    # para Battle-Scarred (lowest=R$ 80 -> 8000 centavos). Com best_ask do book,
    # continua 1.5% (tight) em vez de 1500/8000 = 18.75% (wide, -40 pts de erro).
    v = steam_api.fair_value_verdict(
        80.0, 80.0, spread=1500, best_ask=100000)
    assert v["spread_pct"] == 1.5
    assert v["spread_verdict"] == "tight"


def test_pump_risk_rally_30_dias_reais_em_serie_horaria():
    dia = 86400.0
    base = 1_750_000_000.0
    # 30 dias estáveis em R$ 100, mas com pontos horários nas últimas 48h
    # onde há uma oscilação de +25% só nas últimas 30 horas (mas na média de
    # 30 dias atrás já era R$ 100 e hoje é R$ 105 -> +5%, NÃO +20%).
    hist = [{"time": base + d * dia, "price_median": 100.0, "purchases": 20}
            for d in range(30)]
    # Últimos 2 dias com pontos horários (48 pontos): primeiro cai a 82, volta a 105
    for h in range(48):
        p = 82.0 if h < 24 else 105.0
        hist.append({"time": base + 30 * dia + h * 3600, "price_median": p, "purchases": 2})
    r = signals.pump_risk(hist, volume_history=None)
    assert not any("Subiu" in m for m in r["reasons"])

    # Série real com rally verdadeiro de +30% ao longo de 30 dias -> dispara
    hist_rally = [
        {"time": base + d * dia, "price_median": 100.0 + d * 1.0, "purchases": 10}
        for d in range(35)
    ]
    r2 = signals.pump_risk(hist_rally, volume_history=None)
    assert any("Subiu" in m for m in r2["reasons"])

    # Série curta de 5 dias horários (120 pontos) não deve ser tratada como 30 dias
    hist_curta = [
        {"time": base + h * 3600, "price_median": 50.0 if h < 60 else 90.0, "purchases": 2}
        for h in range(120)
    ]
    r3 = signals.pump_risk(hist_curta, volume_history=None)
    assert not any("Subiu" in m for m in r3["reasons"])


def test_scan_item_alinha_volume_history_e_category_entre_badge_e_nota(monkeypatch):
    dia = 86400.0
    base = 1_750_000_000.0
    hist = [{"time": base + d * dia, "price_median": 100.0 + d * 2.0, "purchases": 10}
            for d in range(35)]
    vol_spike = [{"ts": base + i * dia, "value": 100.0} for i in range(23)] + [
        {"ts": base + (23 + i) * dia, "value": 300.0} for i in range(7)
    ]

    page = {
        "order_book": {"best_ask": 10000, "best_bid": 9900, "spread": 100,
                       "buy_count": 50, "sell_count": 50},
        "order_book_approx": False,
        "price_history": hist,
        "meta": {},
    }
    monkeypatch.setattr(steam_api, "get_market_overview",
                        lambda _n: {"lowest": 168.0, "median": 168.0, "volume": 300})
    monkeypatch.setattr(steam_api, "get_market_page_data", lambda _n: page)
    monkeypatch.setattr(signals, "record_item_price", lambda *a, **k: None)
    monkeypatch.setattr(signals, "record_item_volume", lambda *a, **k: None)
    monkeypatch.setattr(signals, "record_item_supply", lambda *a, **k: None)
    monkeypatch.setattr(signals, "load_item_volume", lambda _n: vol_spike)

    # Com regime_change recente na categoria, ATH e rally são suspensos tanto no
    # selo `pump_risk` quanto na penalidade de `enhanced_score` (sobra só volume = medium).
    monkeypatch.setattr(
        "lodout.valve_events.latest_regime_change",
        lambda cat: {"date": date.today() - timedelta(days=5)} if cat == "Facas" else None,
    )
    res_com_evento = scan_engine.scan_item("★ Karambit | Teste", category="Facas")
    assert res_com_evento is not None
    assert res_com_evento["pump_risk"]["level"] == "medium"
    assert not any(b["factor"] == "pump_risk" for b in res_com_evento["breakdown"])

    # Sem evento de regime, ATH + rally + volume disparam high nos dois lugares
    res_sem_evento = scan_engine.scan_item("★ Karambit | Teste", category="Rifles")
    assert res_sem_evento is not None
    assert res_sem_evento["pump_risk"]["level"] == "high"
    assert any(b["factor"] == "pump_risk" for b in res_sem_evento["breakdown"])
