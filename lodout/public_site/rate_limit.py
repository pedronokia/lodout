"""Limite de tentativas por IP -- janela deslizante em memória.

Hand-rolled, mesmo espírito do disjuntor de rate limit da Steam em
`steam_api.py` (dict de módulo, sem dependência nova) em vez de trazer
Flask-Limiter pra isto. Não é rigoroso sob múltiplos processos/workers
-- cada worker do gunicorn tem sua própria memória, então o limite real
é "por worker", não "por IP globalmente". É uma primeira camada contra
o caso óbvio (um script martelando `/login` ou os formulários de
`/conta`), não a palavra final: tráfego de produção de verdade quer um
backend compartilhado (Redis, por exemplo).
"""
from __future__ import annotations

import time
import threading
from collections import defaultdict, deque
from functools import wraps

from flask import abort, request

_hits: "dict[str, deque]" = defaultdict(deque)
# O gunicorn roda com várias linhas por processo (--threads): sem trava,
# duas requisições ao mesmo tempo podiam passar do limite juntas.
_trava = threading.Lock()

# Presets usados pelas rotas de /login e /conta/* -- um lugar só pra
# ajustar o número sem procurar em cada arquivo de rota.
LOGIN_MAX_HITS, LOGIN_WINDOW_S = 10, 60.0
MUTATION_MAX_HITS, MUTATION_WINDOW_S = 30, 60.0
# Salvar o valor pago na conta (Enter salva e vai ao próximo): quem
# preenche um inventário grande passa de 30 por minuto (1 a cada 2 s) e
# era barrado no 31º (revisão 2026-11-16). Exige login e CSRF e só mexe
# nos dados da própria pessoa; o limite segue valendo contra script.
CUSTO_MAX_HITS, CUSTO_WINDOW_S = 120, 60.0
# "Estou aqui" das abas abertas (online.py): 1 por minuto por aba e 1 a cada página aberta; folga
# para algumas abas atrás do mesmo IP, sem deixar um script inflar a conta.
ONLINE_MAX_HITS, ONLINE_WINDOW_S = 30, 60.0
# Sugestões de nome ao digitar (formulários da conta, 17/11): uma consulta
# a cada ~250 ms de digitação; o limite só barra script.
SUGESTAO_MAX_HITS, SUGESTAO_WINDOW_S = 90, 60.0

# `/api/recommendations` é pública de propósito (pensada pra consumo
# programático -- ver api_docs.html) e mais generosa que os presets de
# formulário. `/api/csp-report` é posta só pelo próprio navegador do
# visitante (nunca por um humano clicando), então um volume normal é
# baixo -- o limite aqui é contra abuso, não contra uso real.
API_MAX_HITS, API_WINDOW_S = 60, 60.0
CSP_REPORT_MAX_HITS, CSP_REPORT_WINDOW_S = 20, 60.0

# `/icone/<hash>.webp` (icon_cache.py) é pública, sem login, e um cache
# miss dispara requisição de rede pro CDN da Steam + grava um arquivo
# novo em disco -- sem limite nenhum, um hash diferente a cada chamada
# vira disco cheio (sem eviction no cache de ícone) e tráfego de saída
# sem fim, achado 2026-10-27 junto da sanitização do hash em
# icon_cache.obter(). Generoso o bastante pra uma página carregar
# dezenas de ícones distintos de uma vez sem barrar uso normal.
ICON_MAX_HITS, ICON_WINDOW_S = 120, 60.0


_MAX_CHAVES = 5000
_TTL_INATIVO_S = 300.0


def _podar_expirados(ts: float) -> None:
    """Remove chaves vazias/inativas e, se ainda passar de `_MAX_CHAVES`,
    descarta as com atividade mais antiga (evita vazamento de memória sob
    tráfego de bots com milhares de IPs distintos)."""
    corte = ts - _TTL_INATIVO_S
    expiradas = [k for k, d in _hits.items() if not d or d[-1] < corte]
    for k in expiradas:
        _hits.pop(k, None)
    if len(_hits) > _MAX_CHAVES:
        excesso = len(_hits) - _MAX_CHAVES
        mais_antigas = sorted(
            _hits.items(), key=lambda par: par[1][-1] if par[1] else 0.0
        )[:excesso]
        for k, _ in mais_antigas:
            _hits.pop(k, None)


def allow(key: str, max_hits: int, window_seconds: float,
         now: "float | None" = None) -> bool:
    """True se `key` ainda tem orçamento na janela; já registra o hit.

    Janela deslizante: descarta hits mais velhos que `window_seconds`
    antes de contar.
    """
    ts = now if now is not None else time.time()
    with _trava:
        if len(_hits) > _MAX_CHAVES:
            _podar_expirados(ts)
        hits = _hits[key]
        corte = ts - window_seconds
        while hits and hits[0] < corte:
            hits.popleft()
        if len(hits) >= max_hits:
            return False
        hits.append(ts)
        return True


def reset() -> None:
    """Limpa todo o estado -- o dict é de módulo e sobrevive entre
    testes na mesma sessão do pytest, mesmo padrão do disjuntor da
    Steam (`steam_api._rate_limit_state`)."""
    with _trava:
        _hits.clear()


def rate_limited(max_hits: int, window_seconds: float):
    """Decorator de rota: `max_hits` por `window_seconds`, por IP+rota.

    Fica ANTES de `login_required`/`csrf_protect` na pilha de
    decorators (mais barato, roda primeiro) -- ver `account.py`/
    `trades_routes.py`/`watchlist_routes.py`.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            ip = request.remote_addr or "desconhecido"
            # `request.endpoint` distingue rota (ex.: "account.login" vs
            # "account.adicionar_posicao") -- um IP barrado numa rota
            # não fica barrado nas outras.
            key = f"{request.endpoint}:{ip}"
            if not allow(key, max_hits, window_seconds):
                abort(429)
            return view(*args, **kwargs)
        return wrapped
    return decorator
