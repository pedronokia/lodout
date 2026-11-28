"""Latência média por rota, em memória.

Aproximado de propósito -- mesmo espírito do `rate_limit.py`: cada
worker do gunicorn tem sua própria memória, então isto é "por worker",
não agregado globalmente entre processos. Suficiente pra notar uma
rota lenta no `/admin` sem trazer infraestrutura de métrica nova
(Prometheus etc.) pra um site de visitante único por request.
"""
from __future__ import annotations

from collections import defaultdict, deque
import threading

_JANELA = 200  # últimas N amostras por rota
_amostras: "dict[str, deque]" = defaultdict(lambda: deque(maxlen=_JANELA))
_trava = threading.Lock()


def registrar(endpoint: str, duracao_ms: float) -> None:
    if not endpoint:
        return
    with _trava:
        _amostras[endpoint].append(duracao_ms)


def resumo() -> list[dict]:
    """[{endpoint, media_ms, contagem}], ordenado por média desc."""
    with _trava:
        copia = [(ep, list(vals)) for ep, vals in _amostras.items() if vals]
    out = []
    for endpoint, valores in copia:
        out.append({
            "endpoint": endpoint,
            "media_ms": round(sum(valores) / len(valores), 1),
            "contagem": len(valores),
        })
    out.sort(key=lambda d: -d["media_ms"])
    return out


def reset() -> None:
    """Limpa o estado -- o dict é de módulo e sobrevive entre testes na
    mesma sessão do pytest (mesmo padrão do disjuntor de rate limit)."""
    with _trava:
        _amostras.clear()
