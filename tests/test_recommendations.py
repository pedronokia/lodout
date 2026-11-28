"""Testes de recommendations.py (candidatos de compra + vigia de venda)."""
from __future__ import annotations

from lodout import recommendations as rec


def _scan_row(name, score, pump_level="low", breakdown=None, **extra):
    row = {
        "name": name,
        "score": score,
        "pump_risk": {"level": pump_level, "flags": 0, "reasons": []},
        "breakdown": breakdown or [],
    }
    row.update(extra)
    return row


# ── buy_candidates ──────────────────────────────────────────────

def test_buy_candidates_ordena_por_score():
    rows = [_scan_row("A", 60), _scan_row("B", 90), _scan_row("C", 75)]
    out = rec.buy_candidates(rows)
    assert [r["name"] for r in out] == ["B", "C", "A"]


def test_buy_candidates_desempata_notas_cortadas_pela_nota_bruta():
    """achado 2026-10-31: enhanced_score() não tem teto antes do clamp
    em 100 -- itens com méritos bem diferentes (ex. 101 bruto vs 115
    bruto) empatavam na nota exibida (100) e ficavam em ordem
    arbitrária (a de chegada em `scan_results`). A ordenação usa a
    soma bruta do breakdown como desempate, sem mudar a nota exibida."""
    rows = [
        _scan_row("Pouco acima do teto", 100,
                  breakdown=[{"factor": "x", "delta": 51, "label": "X (+51)"}]),  # bruto 101
        _scan_row("Bem acima do teto", 100,
                  breakdown=[{"factor": "x", "delta": 65, "label": "X (+65)"}]),  # bruto 115
    ]
    out = rec.buy_candidates(rows)
    assert [r["name"] for r in out] == ["Bem acima do teto", "Pouco acima do teto"]


def test_buy_candidates_exclui_owned():
    rows = [_scan_row("A", 90), _scan_row("B", 80)]
    out = rec.buy_candidates(rows, owned_names={"a"})
    assert [r["name"] for r in out] == ["B"]


def test_buy_candidates_owned_case_insensitive_e_strip():
    rows = [_scan_row("AK-47 | Redline", 90)]
    out = rec.buy_candidates(rows, owned_names={" ak-47 | redline "})
    assert out == []


def test_buy_candidates_filtra_pump_risk_high_por_default():
    rows = [_scan_row("A", 95, pump_level="high"), _scan_row("B", 70)]
    out = rec.buy_candidates(rows)
    assert [r["name"] for r in out] == ["B"]


def test_buy_candidates_max_pump_risk_high_nao_filtra():
    rows = [_scan_row("A", 95, pump_level="high")]
    out = rec.buy_candidates(rows, max_pump_risk="high")
    assert [r["name"] for r in out] == ["A"]


def test_buy_candidates_limit():
    rows = [_scan_row(str(i), i) for i in range(20)]
    out = rec.buy_candidates(rows, limit=3)
    assert len(out) == 3
    assert [r["name"] for r in out] == ["19", "18", "17"]


def test_buy_candidates_reasons_so_fatores_positivos():
    breakdown = [
        {"factor": "mediana", "delta": 20, "label": "Preço baixo (+20)"},
        {"factor": "trend", "delta": -10, "label": "Caindo (-10)"},
        {"factor": "spread", "delta": 15, "label": "Fácil de vender (+15)"},
    ]
    rows = [_scan_row("A", 80, breakdown=breakdown)]
    out = rec.buy_candidates(rows)
    assert out[0]["reasons"] == ["Preço baixo (+20)", "Fácil de vender (+15)"]


def test_buy_candidates_reasons_cap_em_3():
    breakdown = [{"factor": f"f{i}", "delta": 1, "label": f"r{i}"}
                 for i in range(5)]
    rows = [_scan_row("A", 80, breakdown=breakdown)]
    out = rec.buy_candidates(rows)
    assert len(out[0]["reasons"]) == 3


def test_buy_candidates_vazio():
    assert rec.buy_candidates([]) == []


def test_buy_candidates_ignora_linha_sem_name():
    rows = [{"score": 90}, _scan_row("A", 80)]
    out = rec.buy_candidates(rows)
    assert [r["name"] for r in out] == ["A"]
