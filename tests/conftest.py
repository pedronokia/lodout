"""Shared isolation for tests of the public website and scan worker."""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
import urllib.error
from pathlib import Path

import pytest

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="lodout-tests-"))
DATA_DIR_TESTE = _TEST_ROOT / "data"
DATA_DIR_TESTE.mkdir()
os.environ["LODOUT_DATA_DIR"] = str(DATA_DIR_TESTE)
# Nome antigo (ainda aceito como fallback) não pode vazar do ambiente.
os.environ.pop("SKINVAULT_DATA_DIR", None)
atexit.register(shutil.rmtree, _TEST_ROOT, True)


@pytest.fixture(autouse=True)
def _data_dir_isolado():
    yield
    import importlib

    import lodout._paths as paths

    if paths.DATA_DIR != DATA_DIR_TESTE:
        os.environ["LODOUT_DATA_DIR"] = str(DATA_DIR_TESTE)
        importlib.reload(paths)


@pytest.fixture(autouse=True)
def _sem_rede(monkeypatch):
    def _bloqueado(*_args, **_kwargs):
        raise urllib.error.URLError("rede bloqueada na suite de testes")

    monkeypatch.setattr("urllib.request.urlopen", _bloqueado)

    import httpx

    def _httpx_bloqueado(*_args, **_kwargs):
        raise httpx.ConnectError("rede bloqueada na suite de testes")

    monkeypatch.setattr(httpx, "get", _httpx_bloqueado)
    monkeypatch.setattr(httpx, "post", _httpx_bloqueado)
    monkeypatch.setattr(httpx, "request", _httpx_bloqueado)

    class _ClienteBloqueado:
        """`httpx.Client()` (usado por discord_notify.py) não passa por
        `httpx.get`/`post` -- sem isto, um teste que esquecesse o próprio
        mock local faria uma chamada real ao instanciar o client."""

        def __init__(self, *_args, **_kwargs):
            raise httpx.ConnectError("rede bloqueada na suite de testes")

    monkeypatch.setattr(httpx, "Client", _ClienteBloqueado)


@pytest.fixture(autouse=True)
def _sem_espera_de_rate_limit(monkeypatch):
    from lodout import steam_api

    monkeypatch.setattr(steam_api, "RATE_LIMIT_DELAY_S", 0.0)


@pytest.fixture(autouse=True)
def _sem_disjuntores_de_rate_limit():
    from lodout import steam_api
    from lodout.public_site import rate_limit

    steam_api._rate_limit_state.clear()
    steam_api.limpar_cache_paginas()
    rate_limit.reset()
    yield
    steam_api._rate_limit_state.clear()
    steam_api.limpar_cache_paginas()
    rate_limit.reset()


@pytest.fixture(autouse=True)
def _sem_sync_inventario_em_segundo_plano(monkeypatch):
    """O login dispara a sincronização do inventário numa thread
    (inventario.py). Nos testes ela não roda solta: quem quiser testar
    o disparo troca esta função de novo."""
    monkeypatch.setattr(
        "lodout.public_site.inventario.sincronizar_em_segundo_plano",
        lambda steamid: False)


@pytest.fixture(autouse=True)
def _sem_catalogo_de_outro_teste():
    """O banco do catálogo amplo (data/catalogo.sqlite3) é criado por
    test_catalogo; sem isto ele vazava para os testes seguintes e a busca
    da home passava a trazer itens dele."""
    # Os testes gravam preços do catálogo já "em reais": cotação fixa 1,0
    # (em produção ela é medida, ver catalogo.cambio). O teste da
    # conversão desliga isto explicitamente.
    from lodout.public_site import catalogo
    catalogo.CAMBIO_FIXO = 1.0
    catalogo._cambio_cache.update(ts=0.0, valor=None)
    yield
    catalogo.CAMBIO_FIXO = None
    import lodout._paths as paths
    for nome in ("catalogo.sqlite3", "catalogo.sqlite3-wal",
                 "catalogo.sqlite3-shm", "catalogo_estado.json", "catalogo_cambio.json"):
        p = paths.DATA_DIR / nome
        if p.exists():
            p.unlink()


@pytest.fixture(autouse=True)
def _sem_historico_de_notas_nem_online_de_outro_teste():
    """notas_historico.sqlite3 e online.sqlite3 (17/11) nascem no DATA_DIR
    compartilhado: sem isto vazavam de um teste para o outro."""
    yield
    import lodout._paths as paths
    from lodout import prices
    from lodout.public_site import notas_historico, visits
    notas_historico.limpar_cache()
    visits.limpar_cache()
    prices.limpar_cache()
    for base in ("notas_historico.sqlite3", "online.sqlite3"):
        for extra in ("", "-wal", "-shm"):
            p = paths.DATA_DIR / (base + extra)
            if p.exists():
                p.unlink()
