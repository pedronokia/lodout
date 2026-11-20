"""Testes de rate_limit.py (limite de tentativas por IP, em memória)."""
from __future__ import annotations

from lodout.public_site import rate_limit


def test_allow_dentro_do_limite():
    for _ in range(5):
        assert rate_limit.allow("k", max_hits=5, window_seconds=60, now=1.0)


def test_allow_estoura_o_limite():
    for _ in range(5):
        rate_limit.allow("k", max_hits=5, window_seconds=60, now=1.0)
    assert rate_limit.allow("k", max_hits=5, window_seconds=60, now=1.0) is False


def test_janela_deslizante_libera_depois_do_tempo():
    for _ in range(5):
        rate_limit.allow("k", max_hits=5, window_seconds=60, now=0.0)
    assert rate_limit.allow("k", max_hits=5, window_seconds=60, now=0.0) is False
    # 61s depois, os 5 hits antigos ja' saem da janela de 60s.
    assert rate_limit.allow("k", max_hits=5, window_seconds=60, now=61.0) is True


def test_chaves_diferentes_nao_se_misturam():
    for _ in range(5):
        rate_limit.allow("a", max_hits=5, window_seconds=60, now=1.0)
    assert rate_limit.allow("a", max_hits=5, window_seconds=60, now=1.0) is False
    assert rate_limit.allow("b", max_hits=5, window_seconds=60, now=1.0) is True


def test_reset_limpa_tudo():
    for _ in range(5):
        rate_limit.allow("k", max_hits=5, window_seconds=60, now=1.0)
    rate_limit.reset()
    assert rate_limit.allow("k", max_hits=5, window_seconds=60, now=1.0) is True


def test_poda_chaves_expiradas_e_respeita_teto(monkeypatch):
    monkeypatch.setattr(rate_limit, "_MAX_CHAVES", 5)
    monkeypatch.setattr(rate_limit, "_TTL_INATIVO_S", 100.0)
    # 6 chaves antigas em t=10
    for i in range(6):
        assert rate_limit.allow(f"antigo-{i}", max_hits=5, window_seconds=60, now=10.0)
    # Em t=200 (expiradas > 100s), nova chave dispara poda e limpa todas as antigas
    assert rate_limit.allow("novo", max_hits=5, window_seconds=60, now=200.0)
    assert list(rate_limit._hits.keys()) == ["novo"]

    # Mesmo todas ativas, não deixa crescer além de _MAX_CHAVES + 1
    for i in range(10):
        assert rate_limit.allow(f"ativo-{i}", max_hits=5, window_seconds=60, now=200.0 + i)
    assert len(rate_limit._hits) <= 6

