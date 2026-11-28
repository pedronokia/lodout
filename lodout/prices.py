"""Cache de preços em JSON (`data/prices.json`).

Mantém um cache simples nome -> {price, ts} com TTL configurável (6h para
preços válidos, 1h para entradas sem preço) e cache em memória pela identidade
do arquivo para evitar reler o JSON a cada requisição.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from lodout import _paths
from lodout._paths import atomic_write_text

_TTL_SECONDS = 6 * 3600
_NEG_TTL_SECONDS = 60 * 60  # 1h pra entries "sem preco" (None cacheado)
# Override opcional para testes; quando None, resolve dinamicamente via _paths.DATA_DIR.
_DEFAULT_PATH: "Path | None" = None
# Cache em memória pela identidade do arquivo (caminho, mtime_ns, tamanho):
# `_preco_do_dia` na `/conta` e na Watchlist instancia `PriceCache()` por
# request; sem isto, `prices.json` era relido e decodificado do disco toda vez.
_FILE_CACHE: "tuple[tuple[str, int, int], dict[str, dict]] | None" = None


def _caminho_padrao() -> Path:
    if _DEFAULT_PATH is not None:
        return Path(_DEFAULT_PATH)
    return Path(_paths.DATA_DIR) / "prices.json"


def limpar_cache() -> None:
    """Descarta o cache em memória do prices.json (usado por testes)."""
    global _FILE_CACHE
    _FILE_CACHE = None


def _chave_arquivo(p: Path) -> "tuple[str, int, int] | None":
    try:
        st = p.stat()
    except OSError:
        return None
    return (str(p.resolve()), st.st_mtime_ns, st.st_size)


class PriceCache:
    """Cache simples nome -> {price, ts}, persistido em JSON.

    Cacheia tambem entries `None` (itens que o Steam nao tem preco)
    com TTL mais curto, evitando re-fetch repetido a cada startup.
    """

    def __init__(self, path: "Path | str | None" = None,
                 ttl: float = _TTL_SECONDS,
                 neg_ttl: float = _NEG_TTL_SECONDS):
        self.path = Path(path) if path is not None else _caminho_padrao()
        self.ttl = ttl
        self.neg_ttl = neg_ttl
        self._data: dict[str, dict] = {}
        self._load()

    def _load(self) -> None:
        global _FILE_CACHE
        chave = _chave_arquivo(self.path)
        if chave is None:
            self._data = {}
            return
        cached = _FILE_CACHE
        if cached is not None and cached[0] == chave:
            self._data = {k: dict(v) for k, v in cached[1].items()
                          if isinstance(v, dict)}
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            self._data = {}
            return
        if not isinstance(data, dict):
            self._data = {}
            return
        limpo = {k: dict(v) for k, v in data.items() if isinstance(v, dict)}
        _FILE_CACHE = (chave, limpo)
        self._data = {k: dict(v) for k, v in limpo.items()}

    def _save(self) -> None:
        global _FILE_CACHE
        try:
            atomic_write_text(self.path, json.dumps(self._data))
            chave = _chave_arquivo(self.path)
            if chave is not None:
                _FILE_CACHE = (chave, {k: dict(v) for k, v in self._data.items()
                                       if isinstance(v, dict)})
            else:
                _FILE_CACHE = None
        except OSError as e:
            print(f"WARNING: failed to save price cache: {e}",
                  file=__import__('sys').stderr)

    def _entry_valid(self, entry: dict, now: float) -> bool:
        price = entry.get("price")
        ttl = self.ttl if price is not None else self.neg_ttl
        return (now - entry.get("ts", 0)) < ttl

    def has(self, name: str, now: float | None = None) -> bool:
        """Diz se o cache tem entry valida para `name` (inclusive None)."""
        now = time.time() if now is None else now
        entry = self._data.get(name)
        return entry is not None and self._entry_valid(entry, now)

    def get(self, name: str, now: float | None = None) -> float | None:
        now = time.time() if now is None else now
        entry = self._data.get(name)
        if entry and self._entry_valid(entry, now):
            return entry.get("price")
        return None

    def ts(self, name: str, now: float | None = None) -> float | None:
        """Quando o preço válido de `name` foi guardado (epoch), ou None."""
        now = time.time() if now is None else now
        entry = self._data.get(name)
        if entry and self._entry_valid(entry, now) and entry.get("price") is not None:
            return entry.get("ts")
        return None

    def put(self, name: str, price: float | None,
            now: float | None = None) -> None:
        """Cacheia preco. price=None registra "sem preco" (TTL curto)."""
        now = time.time() if now is None else now
        self._data[name] = {"price": price, "ts": now}
        self._save()

    def age(self, name: str, now: float | None = None) -> float | None:
        """Idade da entry em segundos, ou None se nao houver entry.

        Inclui entries expiradas e entries negativas (sem preco). Util
        para UI exibir "cache de Xmin atras" sem invadir self._data.
        """
        entry = self._data.get(name)
        if entry is None:
            return None
        now = time.time() if now is None else now
        return now - entry.get("ts", now)
