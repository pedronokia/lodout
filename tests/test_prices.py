"""Testes do cache de preco (PriceCache)."""
from __future__ import annotations

from lodout import prices


def test_cache_hit_within_ttl(tmp_path):
    c = prices.PriceCache(path=tmp_path / "p.json", ttl=100)
    c.put("AK-47 | Redline", 200.0, now=1000)
    assert c.get("AK-47 | Redline", now=1050) == 200.0   # dentro do TTL
    assert c.get("AK-47 | Redline", now=1200) is None     # expirou
    assert c.get("Inexistente", now=1050) is None


def test_cache_persists_across_instances(tmp_path):
    p = tmp_path / "p.json"
    prices.PriceCache(path=p).put("Glock | Fade", 50.0, now=1000)
    # nova instancia le' do disco
    assert prices.PriceCache(path=p).get("Glock | Fade", now=1001) == 50.0


def test_cache_neg_ttl_expires_sooner(tmp_path):
    """Entradas None (sem preco) expiram com TTL mais curto."""
    c = prices.PriceCache(path=tmp_path / "p.json", ttl=1000, neg_ttl=10)
    c.put("Unknown Item", None, now=1000)
    assert c.get("Unknown Item", now=1005) is None       # dentro do neg_ttl
    assert c.has("Unknown Item", now=1005) is True
    assert c.get("Unknown Item", now=1015) is None       # expirou o neg_ttl


def test_age_method(tmp_path):
    """age() retorna idade em segundos ou None."""
    c = prices.PriceCache(path=tmp_path / "p.json")
    assert c.age("Inexistente") is None
    c.put("AK", 200.0, now=1000)
    age = c.age("AK", now=1050)
    assert age == 50.0


def test_cache_save_oserror(tmp_path):
    """Engole OSError ao salvar."""
    file_path = tmp_path / "afile"
    file_path.write_text("", encoding="utf-8")
    bad = file_path / "p.json"  # file_path e' arquivo, nao diretorio
    c = prices.PriceCache(path=bad, ttl=100)
    c.put("AK", 200.0, now=1000)
    # nao crashou


def test_price_cache_reusa_stat_e_invalida_ao_mudar(tmp_path, monkeypatch):
    import json

    p = tmp_path / "prices.json"
    prices.PriceCache(path=p).put("AK-47 | Slate", 15.0, now=1000.0)
    prices.limpar_cache()

    leituras = []
    real_loads = json.loads

    def espia(raw, *args, **kwargs):
        leituras.append(len(raw))
        return real_loads(raw, *args, **kwargs)

    monkeypatch.setattr(prices.json, "loads", espia)
    c1 = prices.PriceCache(path=p)
    c2 = prices.PriceCache(path=p)
    assert c1.get("AK-47 | Slate", now=1001.0) == 15.0
    assert c2.get("AK-47 | Slate", now=1001.0) == 15.0
    # Segunda instanciação com o mesmo arquivo reaproveita o cache em memória.
    assert len(leituras) == 1

    # Mutar uma instância não contamina o cache compartilhado.
    c1._data["AK-47 | Slate"]["price"] = 999.0
    assert prices.PriceCache(path=p).get("AK-47 | Slate", now=1001.0) == 15.0

    # put() atualiza o cache imediatamente, sem precisar reler o JSON.
    c2.put("AWP | Atheris", 25.0, now=1002.0)
    c3 = prices.PriceCache(path=p)
    assert c3.get("AWP | Atheris", now=1003.0) == 25.0
    assert len(leituras) == 1


def test_price_cache_resolve_data_dir_dinamicamente(tmp_path, monkeypatch):
    from lodout import _paths

    novo_dir = tmp_path / "prices_isolado"
    monkeypatch.setattr(_paths, "DATA_DIR", novo_dir)
    monkeypatch.setattr(prices, "_DEFAULT_PATH", None)
    prices.PriceCache().put("Caixa Teste", 7.5, now=2000.0)
    assert (novo_dir / "prices.json").exists()
    assert prices.PriceCache().get("Caixa Teste", now=2001.0) == 7.5

