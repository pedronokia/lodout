"""Testes do contador de visitas (lodout/public_site/visits.py)."""
from __future__ import annotations

import datetime

from lodout.public_site import visits


def test_dia_local_usa_horario_de_brasilia_nao_utc():
    # achado 2026-11-08: com gmtime() (UTC) o "dia" virava às 21h de
    # Brasília -- 02:30 UTC de 2 de janeiro já são 23:30 de 1º de
    # janeiro no Brasil (UTC-3 fixo, sem horário de verão desde 2019).
    ts = datetime.datetime(
        2024, 1, 2, 2, 30, tzinfo=datetime.timezone.utc).timestamp()
    assert visits.dia_local(ts) == "2024-01-01"


def test_registrar_comeca_em_1(tmp_path):
    p = tmp_path / "visitas.json"
    assert visits.registrar(p) == 1


def test_registrar_incrementa(tmp_path):
    p = tmp_path / "visitas.json"
    visits.registrar(p)
    visits.registrar(p)
    assert visits.registrar(p) == 3


def test_total_nao_incrementa(tmp_path):
    p = tmp_path / "visitas.json"
    visits.registrar(p)
    visits.registrar(p)
    assert visits.total(p) == 2
    assert visits.total(p) == 2


def test_total_sem_arquivo_e_zero(tmp_path):
    p = tmp_path / "visitas.json"
    assert visits.total(p) == 0


def test_serie_por_dia_agrupa_pelo_dia(tmp_path):
    p = tmp_path / "visitas.json"
    ts_dia1 = 1000000.0
    ts_dia2 = ts_dia1 + 86400
    visits.registrar(p, now=ts_dia1)
    visits.registrar(p, now=ts_dia1 + 10)
    visits.registrar(p, now=ts_dia2)
    serie = visits.serie_por_dia(p)
    assert len(serie) == 2
    assert serie[0][1] == 2
    assert serie[1][1] == 1


def test_serie_por_dia_sem_arquivo_e_vazia(tmp_path):
    assert visits.serie_por_dia(tmp_path / "nao_existe.json") == []


def test_serie_por_dia_mantem_so_ultimos_60_dias(tmp_path):
    p = tmp_path / "visitas.json"
    for i in range(65):
        visits.registrar(p, now=1000000.0 + i * 86400)
    assert len(visits.serie_por_dia(p)) == visits._DIAS_MANTIDOS


def test_cache_evita_reler_disco_e_invalida_ao_mudar(tmp_path, monkeypatch):
    p = tmp_path / "visitas.json"
    visits.registrar(p, now=1700000000.0)
    visits.limpar_cache()

    leituras = []
    real_load = visits.load_json_record

    def espia(path, default):
        leituras.append(path)
        return real_load(path, default)

    monkeypatch.setattr(visits, "load_json_record", espia)
    assert visits.total(p) == 1
    assert len(visits.serie_por_dia(p)) == 1
    assert visits.total(p) == 1
    # Uma leitura de disco basta para total() e serie_por_dia().
    assert len(leituras) == 1

    # registrar() atualiza o cache imediatamente: leituras seguintes não relêem disco.
    visits.registrar(p, now=1700000010.0)
    assert len(leituras) == 2
    assert visits.total(p) == 2
    assert visits.serie_por_dia(p)[0][1] == 2
    assert len(leituras) == 2

    # Mutar a lista devolvida não contamina o cache.
    serie = visits.serie_por_dia(p)
    serie.append(("2099-01-01", 999))
    assert len(visits.serie_por_dia(p)) == 1


def test_caminho_padrao_segue_data_dir_dinamicamente(tmp_path, monkeypatch):
    from lodout import _paths

    novo_dir = tmp_path / "dados_isolados"
    monkeypatch.setattr(_paths, "DATA_DIR", novo_dir)
    monkeypatch.setattr(visits, "_DEFAULT_PATH", None)
    assert visits.registrar() == 1
    assert (novo_dir / "visitas.json").exists()
    assert visits.total() == 1


def test_json_corrompido_vai_para_quarentena_sem_cachear(tmp_path):
    p = tmp_path / "visitas.json"
    p.write_text("{json quebrado", encoding="utf-8")
    visits.limpar_cache()
    assert visits.total(p) == 0
    assert visits.serie_por_dia(p) == []
    assert (tmp_path / "visitas.json.corrupt").exists()

