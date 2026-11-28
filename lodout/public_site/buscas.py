"""Contador de termos buscados no dashboard -- agregado, anônimo.

Mesma filosofia de visits.py: nenhum dado por visitante, só
"quantas vezes esse termo foi digitado". Alimenta a página /status (ou
um widget futuro) com "o que a galera mais procura".
"""
from __future__ import annotations

import contextlib
import json
import threading
from pathlib import Path

from lodout import _paths
from lodout._paths import atomic_write_text, load_json_record

try:
    import fcntl
except ImportError:
    fcntl = None

_CAP = 200  # termos distintos guardados -- evita crescimento sem limite
_LOCK = threading.Lock()


def _caminho_padrao() -> Path:
    return Path(_paths.DATA_DIR) / "buscas.json"


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


def registrar(termo: str, path: "Path | str | None" = None) -> None:
    """Soma 1 pro termo (normalizado: minúsculo, sem espaço nas pontas).
    Termo vazio é ignorado."""
    termo = (termo or "").strip().lower()[:80]
    if not termo:
        return
    p = Path(path) if path is not None else _caminho_padrao()
    with _lock_arquivo(p):
        data = load_json_record(p, {})
        if not isinstance(data, dict):
            data = {}
        data[termo] = int(data.get(termo, 0)) + 1
        if len(data) > _CAP:
            # Descarta os menos buscados primeiro -- mantém o topo relevante.
            mais_buscados = sorted(data.items(), key=lambda kv: -kv[1])[:_CAP]
            data = dict(mais_buscados)
        try:
            atomic_write_text(p, json.dumps(data, ensure_ascii=False))
        except OSError:
            pass


def mais_buscados(limite: int = 10,
                  path: "Path | str | None" = None) -> list[tuple[str, int]]:
    """[(termo, contagem)] dos mais buscados, maior primeiro."""
    p = Path(path) if path is not None else _caminho_padrao()
    data = load_json_record(p, {})
    if not isinstance(data, dict):
        return []
    return sorted(data.items(), key=lambda kv: -kv[1])[:limite]
