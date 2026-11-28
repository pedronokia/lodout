"""Testes de regressão do Pacote D (worker, scan_engine, steam_api,
score_backtest, catalogo, db_backup e lazy-load de stickers em cases)."""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
import zipfile

import pytest

from lodout import cases, scan_engine, score_backtest, steam_api
from lodout.public_site import catalogo, db_backup, worker


# ── 1. cases.py: lazy-load de stickers.json ───────────────────────────

def test_cases_nao_carrega_stickers_json_no_import():
    """Importar lodout.cases não deve abrir/parsear stickers.json (~1,1 MB)."""
    code = (
        "import lodout.cases as c, lodout.sticker_data as sd; "
        "assert sd._cache is None and c._ALL_STICKERS_CACHE is None"
    )
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    # Chamada explícita carrega sob demanda e mescla _PREMIUM_STICKERS
    todos = cases.list_all_stickers()
    assert len(todos) > 5000
    assert any(k in todos for k in cases._PREMIUM_STICKERS)


# ── 2. steam_api: _js_unescape e _collect_inventory ───────────────────

def test_js_unescape_nao_engole_caractere_seguinte():
    assert steam_api._js_unescape(r"\u0041B") == "AB"
    assert steam_api._js_unescape(r"\x41B") == "AB"
    assert steam_api._js_unescape(r"\0B") == "\0B"
    assert steam_api._js_unescape(r"\u0041\u0042\x43\0D") == "ABC\0D"
    assert steam_api._js_unescape(r"\uZZZZx") == r"\uZZZZx"


def test_collect_inventory_nao_trata_erro_ou_truncamento_como_vazio_ou_ok(monkeypatch):
    # HTTP 200 com "null", [], {"success": 0} ou {"error": "..."} -> INV_ERROR
    for body in ("null", "[]", '{"success": 0}', '{"success": false}', '{"error": "busy"}'):
        st, items = steam_api._collect_inventory(lambda _s, b=body: (200, b))
        assert st == steam_api.INV_ERROR and items == []

    # Página 2 vazia após more_items=1 -> INV_ERROR (nunca trunca inventário)
    p1 = json.dumps({
        "assets": [{"classid": "1", "instanceid": "1", "amount": 1}],
        "descriptions": [{"classid": "1", "instanceid": "1", "marketable": 1,
                          "market_hash_name": "AK-47 | Redline (Field-Tested)"}],
        "more_items": 1, "last_assetid": "99",
    })
    chamadas = []

    def _pag2_vazia(start):
        chamadas.append(start)
        return (200, p1) if start is None else (200, "{}")

    st, items = steam_api._collect_inventory(_pag2_vazia)
    assert st == steam_api.INV_ERROR and items == []

    # more_items=1 sem last_assetid -> INV_ERROR
    sem_cursor = json.dumps({
        "assets": [{"classid": "1", "instanceid": "1", "amount": 1}],
        "descriptions": [{"classid": "1", "instanceid": "1", "marketable": 1,
                          "market_hash_name": "AK-47"}],
        "more_items": 1,
    })
    st, items = steam_api._collect_inventory(lambda _s: (200, sem_cursor))
    assert st == steam_api.INV_ERROR and items == []

    # Ultrapassou _INV_MAX_PAGES ainda com more_items=1 -> INV_ERROR
    monkeypatch.setattr(steam_api, "_INV_MAX_PAGES", 2)
    st, items = steam_api._collect_inventory(lambda _s: (200, p1))
    assert st == steam_api.INV_ERROR and items == []

    # Inventário legitimamente vazio na página 0 -> INV_EMPTY
    st, items = steam_api._collect_inventory(
        lambda _s: (200, '{"total_inventory_count": 0, "success": 1}'))
    assert st == steam_api.INV_EMPTY and items == []


# ── 3. scan_engine: _sombra em fonte="pagina" e disjuntor interrompível ─

def test_scan_item_fonte_pagina_nao_polui_sombra_com_overview_sintetico(monkeypatch):
    pagina = {
        "order_book": {"best_ask": 10000, "best_bid": 9900, "spread": 100,
                       "buy_count": 50, "sell_count": 10},
        "order_book_approx": False,
        "price_history": [
            {"time": time.time() - 7200, "price_median": 100.0, "purchases": 5},
            {"time": time.time() - 3600, "price_median": 102.0, "purchases": 6},
        ],
    }
    monkeypatch.setattr(steam_api, "get_market_page_data", lambda _n: pagina)
    monkeypatch.setattr(steam_api, "get_market_overview", lambda _n: (_ for _ in ()).throw(AssertionError("não deve chamar")))
    r = scan_engine.scan_item("Item P", fonte="pagina", fator_preco=0.01)
    assert r is not None
    assert r["price"] == 100.0
    assert r["_sombra"] is None


def test_run_full_scan_espera_disjuntor_interrompivel_por_cancelled(monkeypatch):
    dormidas = []
    cancelar = {"flag": False}

    def _sleep(s):
        dormidas.append(s)
        cancelar["flag"] = True

    monkeypatch.setattr(scan_engine.time, "sleep", _sleep)

    def _fake(name, category=None, price_cache=None):
        steam_api._registrar_rate_limit("market_listings")
        return None

    monkeypatch.setattr(scan_engine, "scan_item", _fake)
    rel = {}
    res = scan_engine.run_full_scan(
        {"Rifles": ["A", "B"]},
        cancelled=lambda: cancelar["flag"],
        relatorio=rel,
    )
    assert res == []
    # Dormiu no máximo 1 fatia curta (<= 2s), não o cooldown inteiro (>= 60s)
    assert dormidas and max(dormidas) <= 2.0


# ── 4. db_backup: escrita atômica via tmp + os.replace ────────────────

def test_db_backup_sqlite_e_json_atomicos_via_os_replace(tmp_path, monkeypatch):
    src_db = tmp_path / "public_site.db"
    conn = sqlite3.connect(str(src_db))
    conn.execute("CREATE TABLE t (x INTEGER)")
    conn.execute("INSERT INTO t VALUES (42)")
    conn.commit()
    conn.close()

    src_json = tmp_path / "scanner_last.json"
    src_json.write_text('{"ok": true}', encoding="utf-8")
    out = tmp_path / "backups"

    replaces = []
    real_replace = os.replace

    def _espiao(a, b):
        replaces.append((str(a), str(b)))
        return real_replace(a, b)

    monkeypatch.setattr(db_backup.os, "replace", _espiao)

    bkp_db = db_backup.fazer_backup_se_necessario(src_db, out, now=10_000.0)
    bkp_zip = db_backup.fazer_backup_json_se_necessario({"scanner_last": src_json}, out, now=10_000.0)
    assert bkp_db is not None and bkp_zip is not None
    assert len(replaces) == 2
    assert all(".tmp" in src and ".tmp" not in dst for src, dst in replaces)
    assert list(out.glob("*.tmp")) == []

    # Erro em os.replace limpa o temporário e não cria destino parcial
    def _replace_falha(_a, _b):
        raise OSError("disco cheio")

    monkeypatch.setattr(db_backup.os, "replace", _replace_falha)
    assert db_backup.fazer_backup_se_necessario(src_db, out, now=100_000.0) is None
    assert db_backup.fazer_backup_json_se_necessario({"scanner_last": src_json}, out, now=100_000.0) is None
    assert list(out.glob("*.tmp")) == []


# ── 5. worker: SIGTERM seguro, checkpoint vazio e metadados em rodada_top

def test_worker_sigterm_sem_logging_e_secao_critica(monkeypatch):
    logs = []
    monkeypatch.setattr(worker._logger, "info", lambda *a, **k: logs.append(a))
    monkeypatch.setattr(worker, "_parar", False)
    monkeypatch.setattr(worker, "_escaneando", False)

    with worker._secao_critica():
        worker._ao_receber_sigterm(15, None)
        assert worker._parar is True
    assert logs == []
    assert worker._escaneando is False


def test_worker_run_once_sigterm_antes_do_primeiro_item_nao_grava_checkpoint_vazio(
        monkeypatch, tmp_path):
    cp = tmp_path / "scan_parcial.json"
    monkeypatch.setattr(worker, "_caminho_checkpoint", lambda: cp)
    monkeypatch.setattr(worker, "_caminho_sem_anuncio", lambda: tmp_path / "sem.json")
    monkeypatch.setattr(worker, "_verificar_arquivos_do_jogo", lambda: None)
    monkeypatch.setattr(worker, "_parar", False)
    monkeypatch.setattr(worker.scan_store, "load_last_scan", lambda: None)
    monkeypatch.setattr(worker.scan_store, "load_historico_ciclos", lambda: [])

    def _fake_scan(*_a, **_kw):
        worker._parar = True
        return []

    monkeypatch.setattr(worker.scan_engine, "run_full_scan", _fake_scan)
    assert worker.run_once({"Rifles": ["A"]}) == []
    assert not cp.exists()


def test_worker_rodada_top_herda_icone_e_raridade_do_scan_anterior(monkeypatch):
    scan_anterior = {
        "ts": 1000.0,
        "category": "Todas as categorias",
        "results": [
            {"name": "AK-47 | Redline (Field-Tested)", "score": 80, "price": 50.0,
             "category": "Rifles", "icon": "hash-antigo", "name_color": "eb4b4b",
             "rarity_id": "Rarity_Covert_Weapon"},
        ],
    }
    salvos = {}
    monkeypatch.setattr(worker, "_parar", False)
    monkeypatch.setattr(worker.ranking, "load_snapshots", lambda: [
        {"ts": 1000.0, "items": [{"name": "AK-47 | Redline (Field-Tested)", "position": 1, "score": 80}]}
    ])
    monkeypatch.setattr(worker.scan_store, "load_last_scan", lambda: scan_anterior)
    monkeypatch.setattr(worker.scan_store, "load_historico_ciclos", lambda: [])
    monkeypatch.setattr(worker.scan_store, "save_last_scan",
                        lambda cat, res, now=None: salvos.update(cat=cat, res=res, now=now))
    monkeypatch.setattr(worker.scan_store, "registrar_resultado_rodada_top", lambda *a, **k: None)
    monkeypatch.setattr(worker.scan_engine, "run_full_scan", lambda *_a, **_k: [
        {"name": "AK-47 | Redline (Field-Tested)", "score": 84, "price": 52.0,
         "category": "Rifles", "icon": None, "name_color": None, "rarity_id": None}
    ])

    novos = worker.rodada_top()
    assert len(novos) == 1
    item_salvo = salvos["res"][0]
    assert item_salvo["price"] == 52.0
    assert item_salvo["icon"] == "hash-antigo"
    assert item_salvo["name_color"] == "eb4b4b"
    assert item_salvo["rarity_id"] == "Rarity_Covert_Weapon"


# ── 6. catalogo.varrer: total=0 no meio da fatia e reset de motivo ────

def test_catalogo_varrer_total_zero_meio_da_fatia_vira_pagina_vazia(monkeypatch):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"), ("Pistolas", "P")))
    monkeypatch.setattr(catalogo, "_dormir", lambda *_a, **_k: True)
    respostas = [
        (steam_api.SEARCH_OK, [{"hash_name": "AK-1", "price": 10.0, "listings": 5},
                               {"hash_name": "AK-2", "price": 11.0, "listings": 5}], 50),
        (steam_api.SEARCH_OK, [], 0),  # hiccup: total=0 no meio da fatia
    ]
    it = iter(respostas)
    monkeypatch.setattr(steam_api, "search_market", lambda **_: next(it))
    est = catalogo.varrer(ate_ts=1e12)
    assert est["motivo"] == "pagina_vazia"
    assert est["fatia"] == 0  # não avançou para Pistolas
    assert est["start"] == 1  # avançou 2 - 1 sobreposição e parou antes do hiccup


def test_catalogo_varrer_reseta_motivo_apos_recuperar_de_404(monkeypatch):
    monkeypatch.setattr(catalogo, "FATIAS", (("Rifles", "R"),))
    dormidas = []

    def _dormir(*_a, **_k):
        dormidas.append(1)
        # Deixa tentar a 2a página depois do 404, depois encerra por janela
        return len(dormidas) < 2

    monkeypatch.setattr(catalogo, "_dormir", _dormir)
    respostas = [
        (steam_api.SEARCH_NOT_FOUND, [], 0),
        (steam_api.SEARCH_OK, [{"hash_name": "AK-1", "price": 10.0, "listings": 5}], 50),
    ]
    it = iter(respostas)
    monkeypatch.setattr(steam_api, "search_market", lambda **_: next(it))
    est = catalogo.varrer(ate_ts=1e12)
    assert est["motivo"] == "janela"
    assert est["erro_404_seguidos"] == 0


# ── 7. score_backtest: replay fiel de trend e drawdown ────────────────

def test_score_backtest_repassa_price_history_para_trend_e_drawdown():
    dia = 86400.0
    # 35 dias estáveis em 100 e última semana subindo para 130 -> trend rising (+15)
    serie = [{"time": i * dia, "price_median": 100.0} for i in range(30)] + [
        {"time": (30 + i) * dia, "price_median": 100.0 + (i + 1) * 5.0}
        for i in range(7)
    ]
    res = score_backtest.score_at(
        "AK-47 | Redline (Field-Tested)", serie, serie[-1]["time"])
    assert res is not None
    _score, breakdown = res
    fatores = {b["factor"]: b["delta"] for b in breakdown}
    assert fatores.get("trend") == 15
    assert fatores.get("drawdown") == 5
