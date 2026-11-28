"""Testes do snapshot de ranking."""
from __future__ import annotations

import time

from lodout import ranking


def test_save_snapshot_basic(tmp_path):
    p = tmp_path / "r.json"
    results = [
        {"name": "A", "score": 80},
        {"name": "B", "score": 70},
        {"name": "C", "score": 60},
    ]
    snap = ranking.save_snapshot(results, path=p)
    assert len(snap["items"]) == 3
    assert snap["items"][0]["name"] == "A"
    assert snap["items"][0]["position"] == 1
    assert snap["items"][2]["position"] == 3


def test_save_snapshot_sorts_by_score(tmp_path):
    p = tmp_path / "r.json"
    results = [
        {"name": "Low", "score": 30},
        {"name": "High", "score": 90},
        {"name": "Mid", "score": 60},
    ]
    snap = ranking.save_snapshot(results, path=p)
    names = [it["name"] for it in snap["items"]]
    assert names == ["High", "Mid", "Low"]


def test_save_snapshot_desempata_notas_cortadas_pela_nota_bruta(tmp_path):
    """Mesmo achado de recommendations.buy_candidates (2026-10-31):
    dois itens empatados em 100 (nota cortada) desempatam pela soma
    bruta do breakdown, não pela ordem de chegada."""
    p = tmp_path / "r.json"
    results = [
        {"name": "Pouco acima do teto", "score": 100,
         "breakdown": [{"factor": "x", "delta": 51}]},  # bruto 101
        {"name": "Bem acima do teto", "score": 100,
         "breakdown": [{"factor": "x", "delta": 65}]},  # bruto 115
    ]
    snap = ranking.save_snapshot(results, path=p)
    names = [it["name"] for it in snap["items"]]
    assert names == ["Bem acima do teto", "Pouco acima do teto"]


def test_save_and_load_multiple(tmp_path):
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "A", "score": 50}], path=p)
    ranking.save_snapshot([{"name": "B", "score": 60}], path=p)
    snaps = ranking.load_snapshots(path=p)
    assert len(snaps) == 2


def test_snapshot_cap(tmp_path):
    p = tmp_path / "r.json"
    for i in range(ranking._SNAPSHOT_CAP + 10):
        ranking.save_snapshot([{"name": f"X{i}", "score": i}], path=p)
    snaps = ranking.load_snapshots(path=p)
    assert len(snaps) == ranking._SNAPSHOT_CAP


def test_position_delta_no_previous():
    d = ranking.position_delta("A", 1, None)
    assert d["delta"] == 0
    assert d["prev_pos"] is None
    assert d["label"] == ""


def test_position_delta_subiu():
    prev = {"items": [{"name": "A", "position": 5}]}
    d = ranking.position_delta("A", 2, prev)
    assert d["delta"] == 3
    assert d["prev_pos"] == 5
    assert d["label"] == "+3"


def test_position_delta_caiu():
    prev = {"items": [{"name": "A", "position": 2}]}
    d = ranking.position_delta("A", 5, prev)
    assert d["delta"] == -3
    assert d["label"] == "-3"


def test_position_delta_igual():
    prev = {"items": [{"name": "A", "position": 3}]}
    d = ranking.position_delta("A", 3, prev)
    assert d["delta"] == 0
    assert d["label"] == "="


def test_position_delta_novo():
    prev = {"items": [{"name": "Other", "position": 1}]}
    d = ranking.position_delta("New", 5, prev)
    assert d["label"] == "NOVO"
    assert d["prev_pos"] is None


def test_latest_before(tmp_path):
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "old", "score": 10}], path=p)
    time.sleep(0.01)
    cutoff = time.time()
    time.sleep(0.01)
    ranking.save_snapshot([{"name": "new", "score": 20}], path=p)
    found = ranking.latest_before(cutoff, path=p)
    assert found is not None
    assert found["items"][0]["name"] == "old"


def test_latest_before_none_when_too_old(tmp_path):
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "a", "score": 0}], path=p)
    # cutoff anterior a qualquer snapshot
    assert ranking.latest_before(0, path=p) is None


def test_clear_rankings(tmp_path):
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "A", "score": 50}], path=p)
    assert len(ranking.load_snapshots(path=p)) == 1
    ranking.clear_rankings(path=p)
    assert ranking.load_snapshots(path=p) == []


def test_save_snapshot_corrupted_file(tmp_path):
    """Arquivo existente com dado corrompido e' ignorado."""
    p = tmp_path / "r.json"
    p.write_text("not json", encoding="utf-8")
    snap = ranking.save_snapshot([{"name": "A", "score": 50}], path=p)
    assert len(snap["items"]) == 1


def test_save_snapshot_not_a_list(tmp_path):
    """Arquivo existente com dict (nao lista) e' ignorado."""
    p = tmp_path / "r.json"
    p.write_text('{"bad": "data"}', encoding="utf-8")
    snap = ranking.save_snapshot([{"name": "A", "score": 50}], path=p)
    assert len(snap["items"]) == 1


def test_save_snapshot_oserror_ignored(tmp_path):
    """Segundo save (write) falha silenciosamente."""
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "A", "score": 50}], path=p)
    p.unlink()
    p.mkdir()
    # Falha ao escrever (p e' diretorio) — nao crasha
    snap = ranking.save_snapshot([{"name": "B", "score": 60}], path=p)
    assert len(snap["items"]) == 1


def test_load_snapshots_corrupted_json(tmp_path):
    p = tmp_path / "r.json"
    p.write_text("not json", encoding="utf-8")
    assert ranking.load_snapshots(path=p) == []


def test_clear_rankings_oserror_ignored(tmp_path):
    p = tmp_path / "r.json"
    p.write_text("[]", encoding="utf-8")
    p.unlink()
    p.mkdir()
    ranking.clear_rankings(path=p)  # nao crashou


def test_historico_do_item_por_dia():
    dia = 86400.0
    agora = 100 * dia + 12 * 3600  # meio-dia UTC
    snaps = [
        {"ts": agora - 40 * dia, "items": [{"name": "A", "position": 1}]},
        {"ts": agora - 2 * dia, "items": [{"name": "A", "position": 5}]},
        {"ts": agora - 2 * dia + 3600, "items": [{"name": "A", "position": 2}]},
        {"ts": agora - 1 * dia, "items": [{"name": "B", "position": 1}]},
        {"ts": agora, "items": [{"name": "A", "position": 3}]},
    ]
    h = ranking.historico_do_item("A", dias=30, now=agora, snapshots=snaps,
                                  tz=__import__("datetime").timezone.utc)
    assert len(h["dias"]) == 30
    # O snapshot de 40 dias atrás fica fora da janela.
    assert h["dias_com_ranking"] == 3
    assert h["dias_no_top"] == 2
    assert h["melhor_posicao"] == 2
    assert h["posicao_atual"] == 3
    estados = [d["estado"] for d in h["dias"][-3:]]
    assert estados == ["top", "fora", "top"]
    assert h["dias"][0]["estado"] == "sem_dado"


def test_historico_do_item_sem_snapshots():
    h = ranking.historico_do_item("A", snapshots=[], now=time.time())
    assert h["dias_com_ranking"] == 0
    assert h["posicao_atual"] is None


def test_load_snapshots_cacheia_invalida_e_protege_mutacao(tmp_path, monkeypatch):
    p = tmp_path / "r.json"
    ranking.save_snapshot([{"name": "A", "score": 80}], path=p)

    leituras = []
    orig = ranking.load_json_record

    def espiao(*a, **k):
        leituras.append(a[0])
        return orig(*a, **k)

    monkeypatch.setattr(ranking, "load_json_record", espiao)
    s1 = ranking.load_snapshots(path=p)
    s2 = ranking.load_snapshots(path=p)
    assert len(leituras) == 1
    assert len(s1) == 1 and len(s2) == 1
    # Mutar a lista devolvida não corrompe o cache.
    s1.append({"ts": 0, "items": []})
    assert len(ranking.load_snapshots(path=p)) == 1

    # Gravar novo snapshot invalida o cache imediatamente.
    ranking.save_snapshot([{"name": "B", "score": 90}], path=p)
    assert len(ranking.load_snapshots(path=p)) == 2
    ranking.clear_rankings(path=p)
    assert ranking.load_snapshots(path=p) == []


def test_scan_store_load_last_scan_cacheia_e_devolve_copias(tmp_path, monkeypatch):
    from lodout import scan_store
    p = tmp_path / "scan.json"
    scan_store.save_last_scan("Rifles", [{"name": "AK-47", "score": 85}], path=p, now=1000.0)

    chamadas_json = []
    orig_loads = scan_store.json.loads

    def espiao(texto):
        chamadas_json.append(1)
        return orig_loads(texto)

    monkeypatch.setattr(scan_store.json, "loads", espiao)
    r1 = scan_store.load_last_scan(path=p)
    r2 = scan_store.load_last_scan(path=p)
    assert len(chamadas_json) == 1
    assert r1["results"][0]["name"] == "AK-47"
    # Mutar item devolvido não contamina o cache.
    r1["results"][0]["price_fmt"] = "MUTADO"
    assert "price_fmt" not in r2["results"][0]
    assert "price_fmt" not in scan_store.load_last_scan(path=p)["results"][0]

    # Novo save invalida o cache imediatamente.
    scan_store.save_last_scan("Rifles", [{"name": "AWP", "score": 90}], path=p, now=2000.0)
    r3 = scan_store.load_last_scan(path=p)
    assert r3["results"][0]["name"] == "AWP"


def test_notas_historico_ranking_consistente_cacheia_e_invalida(monkeypatch):
    from lodout.public_site import notas_historico as nh

    agora = time.time()
    nh.gravar_snapshot(
        {"ts": agora - 3600, "items": [{"name": "Item A", "score": 82, "position": 1}]},
        agora=agora,
    )
    conexoes = []
    orig_conectar = nh._conectar

    def espiao():
        conexoes.append(1)
        return orig_conectar()

    monkeypatch.setattr(nh, "_conectar", espiao)
    r1 = nh.ranking_consistente(7)
    r2 = nh.ranking_consistente(7)
    # 1ª chamada abre 1 única conexão; 2ª sai direto do cache (0 conexões).
    assert len(conexoes) == 1
    assert r1["itens"][0]["name"] == "Item A"
    assert r2["itens"][0]["name"] == "Item A"
    r1["itens"][0]["name"] = "MUTADO"
    assert nh.ranking_consistente(7)["itens"][0]["name"] == "Item A"

    # Nova gravação invalida o cache imediatamente.
    nh.gravar_snapshot(
        {"ts": agora, "items": [{"name": "Item B", "score": 95, "position": 1}]},
        agora=agora,
    )
    r3 = nh.ranking_consistente(7)
    nomes = {i["name"] for i in r3["itens"]}
    assert nomes == {"Item A", "Item B"}
