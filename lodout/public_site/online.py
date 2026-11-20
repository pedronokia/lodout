"""Quantas pessoas estão no site agora (pedido do usuário, 17/11).

Cada aba aberta manda um "estou aqui" a cada minuto (static/online.js),
só enquanto está visível, com um código aleatório que vive no
sessionStorage da aba: some quando ela fecha. Sem cookie, sem IP, sem
ligação com a conta. Aqui guardamos só (código, hora) e contamos os
códigos vistos nos últimos `JANELA_S`; o que passa de `GUARDA_S` é
apagado na próxima gravação.

SQLite próprio (`data/online.sqlite3`): o gunicorn roda em vários
processos, então a contagem precisa de um lugar comum, e fora do banco
das contas.
"""
from __future__ import annotations

import logging
import re
import sqlite3
import threading
import time
from pathlib import Path

from lodout import _paths

_logger = logging.getLogger(__name__)
_INIT_LOCK = threading.Lock()
_INICIALIZADOS: set[tuple[str, int, int]] = set()

JANELA_S = 180.0   # "agora" = deu sinal nos últimos 3 min (aviso a cada 1 min)
GUARDA_S = 600.0   # nada fica guardado mais que 10 min
_ID_OK = re.compile(r"^[0-9a-f]{16,64}$")


def _caminho() -> Path:
    return Path(_paths.DATA_DIR) / "online.sqlite3"


def _chave_arquivo(p: Path) -> "tuple[str, int, int] | None":
    try:
        st = p.stat()
    except OSError:
        return None
    if st.st_size == 0:
        return None
    return (str(p.resolve()), st.st_dev, st.st_ino)


def _conectar() -> sqlite3.Connection:
    p = _caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    chave = _chave_arquivo(p)
    conn = sqlite3.connect(str(p), timeout=2)
    conn.execute("PRAGMA busy_timeout=2000")
    conn.execute("PRAGMA synchronous=NORMAL")
    if chave is None or chave not in _INICIALIZADOS:
        with _INIT_LOCK:
            if chave is None or chave not in _INICIALIZADOS:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("CREATE TABLE IF NOT EXISTS presenca (id TEXT PRIMARY KEY, ts REAL NOT NULL)")
                conn.commit()
                nova_chave = _chave_arquivo(p)
                if nova_chave is not None:
                    _INICIALIZADOS.add(nova_chave)
    return conn


def id_valido(codigo: object) -> bool:
    return isinstance(codigo, str) and bool(_ID_OK.match(codigo))


def marcar(codigo: str, agora: "float | None" = None) -> None:
    """Registra o sinal de uma aba e apaga os antigos."""
    if not id_valido(codigo):
        raise ValueError("código inválido")
    agora = time.time() if agora is None else agora
    conn = _conectar()
    try:
        with conn:
            conn.execute("INSERT INTO presenca (id, ts) VALUES (?, ?) "
                         "ON CONFLICT(id) DO UPDATE SET ts = excluded.ts", (codigo, agora))
            conn.execute("DELETE FROM presenca WHERE ts < ?", (agora - GUARDA_S,))
    finally:
        conn.close()


def contar(agora: "float | None" = None) -> int:
    """Abas que deram sinal nos últimos `JANELA_S`. 0 se não der para ler."""
    agora = time.time() if agora is None else agora
    if not _caminho().exists():
        return 0
    try:
        conn = _conectar()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM presenca WHERE ts >= ?",
                                    (agora - JANELA_S,)).fetchone()[0])
        finally:
            conn.close()
    except sqlite3.Error:
        _logger.warning("contagem de quem está no site falhou", exc_info=True)
        return 0
