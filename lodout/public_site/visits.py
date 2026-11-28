"""Contador de visitas simples e privado -- só pra saber se alguém usa.

Sem cookie, sem IP, sem nada por visitante (a página de privacidade já
promete isso). Total acumulado + série por dia (pro gráfico em /status).
Não é analytics de verdade, é um termômetro.
"""
from __future__ import annotations

import contextlib
import datetime
import json
import threading
import time
from pathlib import Path

from lodout import _paths
from lodout._paths import atomic_write_text, load_json_record
from lodout.public_site.fmt import FUSO_BR

try:
    import fcntl
except ImportError:
    fcntl = None

# Override opcional para testes antigos que fazem monkeypatch em `_DEFAULT_PATH`.
# Quando None, o caminho é resolvido dinamicamente a partir de `_paths.DATA_DIR`.
_DEFAULT_PATH: "Path | None" = None
_DIAS_MANTIDOS = 60
_LOCK = threading.Lock()
# Cache em memória pela identidade do arquivo (caminho, mtime_ns, tamanho):
# `_inject_visitas_no_rodape()` consulta `serie_por_dia()` e `total()` em toda
# página HTML -- sem cache, visitas.json era lido e decodificado 2-4x por visita.
# Tupla imutável (chave, total, serie) evita leitura parcial entre threads.
_CACHE: "tuple[tuple[str, int, int], int, tuple[tuple[str, int], ...]] | None" = None


def _caminho_padrao() -> Path:
    if _DEFAULT_PATH is not None:
        return Path(_DEFAULT_PATH)
    return Path(_paths.DATA_DIR) / "visitas.json"


def limpar_cache() -> None:
    """Descarta o cache em memória (usado por testes)."""
    global _CACHE
    _CACHE = None


def _chave_arquivo(p: Path) -> "tuple[str, int, int] | None":
    try:
        st = p.stat()
    except OSError:
        return None
    return (str(p.resolve()), st.st_mtime_ns, st.st_size)


def _ler(p: Path) -> "tuple[int, tuple[tuple[str, int], ...]]":
    global _CACHE
    chave = _chave_arquivo(p)
    if chave is None:
        return 0, ()
    cached = _CACHE
    if cached is not None and cached[0] == chave:
        return cached[1], cached[2]
    data = load_json_record(p, {"total": 0, "por_dia": {}})
    if not isinstance(data, dict):
        return 0, ()
    total_val = int(data.get("total") or 0)
    por_dia = data.get("por_dia") or {}
    serie_val = tuple(sorted(por_dia.items())) if isinstance(por_dia, dict) else ()
    # Só guarda no cache se o arquivo não foi movido para quarentena.
    if _chave_arquivo(p) == chave:
        _CACHE = (chave, total_val, serie_val)
    return total_val, serie_val


@contextlib.contextmanager
def _lock_arquivo(alvo: Path):
    """Serializa leitura-modificação-escrita entre threads e workers do gunicorn."""
    with _LOCK:
        if fcntl is None:
            yield
            return
        lock_path = Path(f"{alvo}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with open(lock_path, "a") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)


def dia_local(ts: "float | None" = None) -> str:
    """Chave YYYY-MM-DD do dia no horário de Brasília.

    achado 2026-11-08: a série usava gmtime() (UTC) -- o "dia" virava
    às 21h de Brasília, quase 3h antes da meia-noite real do
    visitante, fazendo o contador "hoje" zerar cedo demais."""
    momento = time.time() if ts is None else ts
    return datetime.datetime.fromtimestamp(
        momento, tz=FUSO_BR).strftime("%Y-%m-%d")


def registrar(path: "Path | str | None" = None,
              now: "float | None" = None) -> int:
    """Soma 1 (total e no dia de hoje) e grava. Devolve o total atualizado.

    `path=None` é resolvido aqui dentro, não como default de parâmetro,
    para que testes possam apontar para um arquivo isolado.
    """
    global _CACHE
    p = Path(path) if path is not None else _caminho_padrao()
    with _lock_arquivo(p):
        data = load_json_record(p, {"total": 0, "por_dia": {}})
        total_val = int(data.get("total") or 0) + 1
        por_dia = data.get("por_dia") or {}
        hoje = dia_local(now)
        por_dia[hoje] = int(por_dia.get(hoje, 0)) + 1
        # Mantém só os últimos N dias -- série de visitas não precisa crescer
        # sem limite (diferente do histórico de ciclos, que já tem cap próprio).
        if len(por_dia) > _DIAS_MANTIDOS:
            for dia_antigo in sorted(por_dia)[:-_DIAS_MANTIDOS]:
                del por_dia[dia_antigo]
        try:
            atomic_write_text(p, json.dumps({"total": total_val, "por_dia": por_dia}))
            nova_chave = _chave_arquivo(p)
            if nova_chave is not None:
                _CACHE = (nova_chave, total_val, tuple(sorted(por_dia.items())))
            else:
                _CACHE = None
        except OSError:
            pass
        return total_val


def total(path: "Path | str | None" = None) -> int:
    """Total atual, sem incrementar."""
    p = Path(path) if path is not None else _caminho_padrao()
    total_val, _serie = _ler(p)
    return total_val


def serie_por_dia(path: "Path | str | None" = None) -> list[tuple[str, int]]:
    """[(dia, contagem)] em ordem cronológica, mais antigo primeiro."""
    p = Path(path) if path is not None else _caminho_padrao()
    _total, serie = _ler(p)
    return list(serie)
