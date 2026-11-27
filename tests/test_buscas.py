"""Testes do contador de termos buscados (lodout/public_site/buscas.py)."""
from __future__ import annotations

from lodout.public_site import buscas


def test_registrar_e_contar(tmp_path):
    p = tmp_path / "buscas.json"
    buscas.registrar("AK-47", p)
    buscas.registrar("ak-47", p)  # normaliza minusculo
    buscas.registrar("awp", p)
    assert buscas.mais_buscados(path=p) == [("ak-47", 2), ("awp", 1)]


def test_registrar_vazio_ignorado(tmp_path):
    p = tmp_path / "buscas.json"
    buscas.registrar("", p)
    buscas.registrar("   ", p)
    assert buscas.mais_buscados(path=p) == []


def test_mais_buscados_respeita_limite(tmp_path):
    p = tmp_path / "buscas.json"
    for i in range(5):
        buscas.registrar(f"item{i}", p)
    assert len(buscas.mais_buscados(limite=3, path=p)) == 3


def test_mais_buscados_sem_arquivo_e_vazio(tmp_path):
    assert buscas.mais_buscados(path=tmp_path / "nao_existe.json") == []


def test_registrar_respeita_teto_e_trata_json_invalido(tmp_path, monkeypatch):
    p = tmp_path / "buscas.json"
    p.write_text('["nao", "dict"]', encoding="utf-8")
    assert buscas.mais_buscados(path=p) == []

    monkeypatch.setattr(buscas, "_CAP", 3)
    for termo in ("a", "a", "b", "b", "c", "c", "d"):
        buscas.registrar(termo, p)
    topo = buscas.mais_buscados(limite=10, path=p)
    assert len(topo) == 3
    assert {t for t, _ in topo} == {"a", "b", "c"}


def test_caminho_padrao_resolve_data_dir_dinamicamente(tmp_path, monkeypatch):
    from lodout import _paths
    novo_dir = tmp_path / "outro_data"
    novo_dir.mkdir()
    monkeypatch.setattr(_paths, "DATA_DIR", novo_dir)
    buscas.registrar("karambit")
    assert (novo_dir / "buscas.json").exists()
    assert buscas.mais_buscados() == [("karambit", 1)]
