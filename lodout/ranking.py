"""Snapshots de ranking do scanner.

Cada snapshot grava {ts, items: [{name, score, position}]}.
Permite comparar posicao atual vs anterior (delta).
Cap em 50 snapshots (volume historico controlado).
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from lodout._paths import (
    DATA_DIR, atomic_write_text, load_json_record,
)
from lodout import signals

_RANKINGS_PATH = DATA_DIR / "rankings.json"
# 150 = ~37 dias com o worker de 6 em 6h -- margem folgada: o /ranking hoje
# só compara com ~24h atrás (`_snapshot_de_comparacao` em public_site/server.py).
_SNAPSHOT_CAP = 150
# Cache em memória dos snapshots de rankings.json, pela identidade do
# arquivo (caminho, mtime_ns, tamanho): o arquivo só muda a cada coleta,
# mas era relido inteiro em toda visita à home e ao /ranking.
_CACHE_SNAPSHOTS: dict = {"chave": None, "dados": []}


def save_snapshot(results: list[dict],
                  path: Path | str = _RANKINGS_PATH) -> dict:
    """Grava snapshot dos resultados de um scan.

    results: lista de {name, score, ...} ordenada por score desc.
    Retorna o snapshot gravado.
    """
    # Desempate pela nota bruta (antes do clamp em 100) -- mesmo
    # motivo de recommendations.buy_candidates: sem isso, itens
    # empatados em 100 (comum: o modelo não tem teto antes do clamp)
    # ficavam em ordem arbitrária no Top 20.
    sorted_r = sorted(results, key=lambda r: (
        -r.get("score", 0), -signals.raw_score(r.get("breakdown"))))
    items = [
        {
            "name": r["name"],
            "score": int(r.get("score", 0)),
            "position": i + 1,
        }
        for i, r in enumerate(sorted_r)
    ]
    snapshot = {"ts": time.time(), "items": items}

    p = Path(path)
    data = load_json_record(p, [])
    if not isinstance(data, list):
        data = []
    data.append(snapshot)
    if len(data) > _SNAPSHOT_CAP:
        data = data[-_SNAPSHOT_CAP:]
    try:
        atomic_write_text(p, json.dumps(data, indent=2))
        _CACHE_SNAPSHOTS["chave"] = None
    except OSError as e:
        print(f"WARNING: failed to save ranking snapshot: {e}",
              file=__import__('sys').stderr)
    return snapshot


def load_snapshots(path: Path | str = _RANKINGS_PATH) -> list[dict]:
    """Retorna todos os snapshots (mais recente por ultimo)."""
    p = Path(path)
    try:
        st = p.stat()
    except OSError:
        return []
    chave = (str(p.resolve()), st.st_mtime_ns, st.st_size)
    if _CACHE_SNAPSHOTS["chave"] != chave:
        data = load_json_record(p, [])
        _CACHE_SNAPSHOTS["dados"] = data if isinstance(data, list) else []
        _CACHE_SNAPSHOTS["chave"] = chave
    return list(_CACHE_SNAPSHOTS["dados"])


def latest_before(ts: float, path: Path | str = _RANKINGS_PATH) -> dict | None:
    """Retorna o snapshot mais recente anterior a ts (ex: snapshot de uma semana atras)."""
    snaps = load_snapshots(path)
    candidates = [s for s in snaps if s.get("ts", 0) < ts]
    return candidates[-1] if candidates else None


def position_delta(name: str, current_position: int,
                   previous: dict | None) -> dict:
    """Calcula mudanca de posicao do item entre snapshot anterior e atual.

    Retorna:
    - {delta: int, prev_pos: int, label: str}   - subiu/caiu/igual
    - {delta: 0, prev_pos: None, label: 'NOVO'} - nao estava antes
    - {delta: 0, prev_pos: None, label: ''}     - sem snapshot anterior
    """
    if not previous or not previous.get("items"):
        return {"delta": 0, "prev_pos": None, "label": ""}
    for it in previous["items"]:
        if it.get("name") == name:
            prev = int(it.get("position", 0))
            delta = prev - current_position  # positivo = subiu
            if delta > 0:
                label = f"+{delta}"
            elif delta < 0:
                label = f"{delta}"
            else:
                label = "="
            return {"delta": delta, "prev_pos": prev, "label": label}
    return {"delta": 0, "prev_pos": None, "label": "NOVO"}
