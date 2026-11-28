"""Recomendações -- filtra e ordena candidatos do último scan.

Retorna as melhores notas do último scan, descontando itens já presentes
no portfólio e alertas de subida rápida acima do limite escolhido.

Não inventa sinal novo: só reusa o que `signals.py`/`cases.py` já
calculam. Mesma regra do resto do projeto -- nunca prever futuro, só
descrever dados (AGENTS.md).
"""
from __future__ import annotations

from lodout import signals

_RISK_ORDER = {"low": 0, "medium": 1, "high": 2}


def buy_candidates(scan_results: list[dict],
                   owned_names: "set[str] | None" = None,
                   max_pump_risk: str = "medium",
                   limit: int = 10) -> list[dict]:
    """Candidatos de compra: melhores notas do último scan.

    scan_results: linhas no formato de `ScannerScreen._scan_item`
    (precisa de `name` e `score`; usa `price`/`verdict`/`case_label`/
    `pump_risk`/`breakdown`/`is_container` quando vierem).

    Descarta o que já está no portfólio (`owned_names`) e o que tem
    alerta de subida rápida acima de `max_pump_risk` ("low" exclui
    qualquer alerta; "high" não filtra nada por risco).

    Cada item sai com `reasons`: até 3 motivos factuais (os fatores que
    SOMARAM pontos no score), extraídos do próprio breakdown -- não é
    texto novo, é o que `enhanced_score` já calculou.
    """
    owned = {n.strip().lower() for n in (owned_names or ())}
    max_n = _RISK_ORDER.get(max_pump_risk, 1)
    out = []
    for r in scan_results:
        name = r.get("name")
        if not name or name.strip().lower() in owned:
            continue
        risco = (r.get("pump_risk") or {}).get("level", "low")
        if _RISK_ORDER.get(risco, 0) > max_n:
            continue
        reasons = [b["label"] for b in (r.get("breakdown") or [])
                   if b.get("delta", 0) > 0][:3]
        out.append({**r, "reasons": reasons})
    # Desempate pela nota bruta (antes do clamp em 100) -- sem isso,
    # itens empatados na nota exibida ficavam em ordem arbitrária.
    out.sort(key=lambda r: (
        -(r.get("score") or 0), -signals.raw_score(r.get("breakdown"))))
    return out[:limit]
