"""Schema SQLite do site público -- a ÚNICA parte do projeto com banco.

Guarda so' conta (steamid publico, via Steam OpenID -- ver steam_openid.py)
e dado pessoal por usuario (`user_data`, uma linha por `kind`: "portfolio"
por agora, "trades"/"watchlist"/etc. nas fases seguintes, reusando a MESMA
tabela). O resto do site (scan_store.json, rankings.json) continua em JSON
global, sem dono -- isso aqui e' so' pro que PRECISA de dono.

`sqlite3` e' stdlib: zero dependencia nova. Um arquivo `public_site.db` em
`DATA_DIR` (mesma pasta do scan_store.json da Fase 1).
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from lodout._paths import DATA_DIR

_DB_PATH = DATA_DIR / "public_site.db"
_CONNECT_TIMEOUT_S = 10.0
_BUSY_TIMEOUT_MS = 10_000
_INIT_LOCK = threading.Lock()
_INICIALIZADOS: set[tuple[str, int, int]] = set()

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    steamid TEXT PRIMARY KEY,
    persona_name TEXT,
    avatar_url TEXT,
    created_ts REAL,
    last_login_ts REAL
);
CREATE TABLE IF NOT EXISTS user_data (
    steamid TEXT NOT NULL,
    kind TEXT NOT NULL,
    payload TEXT NOT NULL,
    updated_ts REAL,
    PRIMARY KEY (steamid, kind)
);
"""


def _chave_arquivo(p: Path) -> "tuple[str, int, int] | None":
    try:
        st = p.stat()
    except OSError:
        return None
    if st.st_size == 0:
        return None
    return (str(p.resolve()), st.st_dev, st.st_ino)


def connect(path: "Path | str | None" = None) -> sqlite3.Connection:
    """Abre uma conexao nova, com o schema garantido.

    `path=None` resolve `_DB_PATH` AQUI DENTRO (em tempo de chamada), nao
    como default de parametro, para permitir que testes e chamadores
    escolham um caminho atual. Cada chamador abre e fecha a propria
    conexao; nao ha' conexao global compartilhada entre requests.
    """
    p = Path(path) if path is not None else _DB_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    # Checa ANTES do connect: se o arquivo foi apagado e recriado, o SO
    # pode reutilizar o mesmo inode; aqui ele ainda não existe (ou tem 0 B).
    chave = _chave_arquivo(p)
    conn = sqlite3.connect(str(p), timeout=_CONNECT_TIMEOUT_S)
    conn.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA foreign_keys=ON")
    # synchronous=NORMAL e' por conexao e par padrao de WAL (skill
    # sqlite-database-expert, 2026-11-04): com WAL o SO ja' garante
    # consistencia apos crash do processo; FULL so' importa pra
    # sobreviver crash do SO/queda de energia, que este site nao promete.
    conn.execute("PRAGMA synchronous=NORMAL")

    # WAL e DDL so' precisam rodar uma vez por arquivo -- evita lock de
    # escrita a cada request HTTP com varias threads do gunicorn + worker.
    if chave is None or chave not in _INICIALIZADOS:
        with _INIT_LOCK:
            if chave is None or chave not in _INICIALIZADOS:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(_SCHEMA)
                nova_chave = _chave_arquivo(p)
                if nova_chave is not None:
                    _INICIALIZADOS.add(nova_chave)
    return conn
