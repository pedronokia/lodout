"""Testes de regressão do Pacote B (cabeçalhos HTTP, atomicidade de conta,
limites de entrada, estabilidade web, performance e qualidade de dados)."""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from lodout import signals
from lodout.public_site import (
    buscas,
    db,
    db_backup,
    inventario,
    latencia,
    notas_historico,
    online,
    profile_fetcher as pf,
    rate_limit,
    server,
    user_portfolio,
    user_store,
    user_trocas,
    user_vendidos,
    user_watchlist,
)


from lodout.public_site.inventario import (
    sincronizar_em_segundo_plano as _SYNC_BG_REAL,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr("lodout.public_site.db._DB_PATH", tmp_path / "site.db")
    monkeypatch.setattr("lodout.public_site.server._SECRET_KEY_PATH", tmp_path / "secret.key")
    monkeypatch.setattr("lodout.public_site.server._ERROR_LOG_PATH", tmp_path / "errors.log")
    monkeypatch.setattr("lodout.public_site.visits._DEFAULT_PATH", tmp_path / "visits.json")
    monkeypatch.setattr("lodout.public_site.buscas._caminho_padrao", lambda: tmp_path / "buscas.json")
    monkeypatch.setattr(db_backup, "_BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(pf, "_AVATARS_DIR", tmp_path / "avatars")
    monkeypatch.setattr(pf, "_PROFILES_PATH", tmp_path / "profiles.json")
    monkeypatch.setattr(pf, "_LOCK_PATH", tmp_path / "profiles.json.lock")
    app = server.create_app()
    app.config["TESTING"] = True
    return app.test_client()


def _logar(client, steamid: str = "76561198000009999") -> str:
    user_store.upsert_user(steamid, persona_name="Tester", avatar_url="https://avatars.steamstatic.com/t.jpg")
    with client.session_transaction() as sess:
        sess["steamid"] = steamid
        sess["csrf_token"] = "tok-pacote-b"
    return "tok-pacote-b"


# ── 1. Cabeçalhos HTTP, cache e sanitização ───────────────────────────

def test_headers_cache_admin_export_avatar_sw_sitemap(client, tmp_path, monkeypatch):
    monkeypatch.setattr(server, "_ADMIN_PASSWORD_HASH", "hash-teste-admin")
    # Admin HTML + downloads privados
    with client.session_transaction() as sess:
        sess["admin"] = time.time()
    r_admin = client.get("/admin")
    assert r_admin.status_code == 200
    assert r_admin.headers.get("Cache-Control") == "private, no-store"

    (tmp_path / "backups").mkdir(exist_ok=True)
    (tmp_path / "backups" / "public_site-20261128-010000.db").write_bytes(b"sqlite")
    r_bkp = client.get("/admin/backup/public_site-20261128-010000.db")
    assert r_bkp.status_code == 200
    assert r_bkp.headers.get("Cache-Control") == "private, no-store"

    (tmp_path / "errors.log").write_text("erro teste\n", encoding="utf-8")
    r_log = client.get("/admin/log-bruto")
    assert r_log.status_code == 200
    assert r_log.headers.get("Cache-Control") == "private, no-store"

    # Conta: exportar JSON e avatar
    sid = "76561198000009901"
    _logar(client, sid)
    r_exp = client.get("/conta/exportar")
    assert r_exp.status_code == 200
    assert r_exp.headers.get("Cache-Control") == "private, no-store"

    (tmp_path / "avatars").mkdir(exist_ok=True)
    (tmp_path / "avatars" / f"{sid}.jpg").write_bytes(b"\xff\xd8\xff\xd9")
    r_av = client.get("/conta/avatar.jpg")
    assert r_av.status_code == 200
    assert r_av.headers.get("Cache-Control") == "private, no-cache"

    # Públicos: /sw.js e /sitemap.xml
    r_sw = client.get("/sw.js")
    assert r_sw.status_code == 200
    assert r_sw.headers.get("Cache-Control") == "no-cache"
    assert r_sw.headers.get("Service-Worker-Allowed") == "/"

    r_sm = client.get("/sitemap.xml")
    assert r_sm.status_code == 200
    assert r_sm.headers.get("Cache-Control") == "public, max-age=300"


def test_icone_cache_sanitiza_hash_antes_do_redirect(client, monkeypatch):
    monkeypatch.setattr("lodout.public_site.icon_cache.obter", lambda *_a, **_k: None)
    assert client.get("/icone/$$$.webp").status_code == 404
    r = client.get("/icone/abc!def.webp")
    assert r.status_code == 302
    assert "/abcdef/192fx192f" in r.headers["Location"]
    assert "!" not in r.headers["Location"]


# ── 2. Persistência, concorrência e integridade da conta ──────────────

def test_upsert_user_coalesce_preserva_nome_e_avatar_em_falha(tmp_path):
    p = tmp_path / "u.db"
    user_store.upsert_user("10", persona_name="Alice", avatar_url="https://avatars.steamstatic.com/a.jpg", path=p)
    user_store.upsert_user("10", persona_name=None, avatar_url=None, path=p)
    u = user_store.get_user("10", path=p)
    assert u["persona_name"] == "Alice"
    assert u["avatar_url"] == "https://avatars.steamstatic.com/a.jpg"


def test_load_user_json_loga_corrupcao_e_devolve_default(tmp_path, caplog):
    p = tmp_path / "u.db"
    conn = db.connect(p)
    with conn:
        conn.execute(
            "INSERT INTO user_data (steamid, kind, payload, updated_ts) VALUES (?, ?, ?, ?)",
            ("11", "portfolio", "{json-quebrado", 1.0),
        )
    conn.close()
    with caplog.at_level("WARNING"):
        assert user_store.load_user_json("11", "portfolio", [], path=p) == []
    assert any("JSON inválido" in r.message for r in caplog.records)


def test_update_user_json_concorrente_nao_perde_atualizacoes(tmp_path):
    p = tmp_path / "c.db"
    sid = "76561198000001111"
    for i in range(12):
        user_portfolio.add_position(sid, f"Item {i}", None, 1, path=p)

    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = [
            pool.submit(user_portfolio.update_position_cost, sid, f"Item {i}", float(i + 1), path=p)
            for i in range(12)
        ]
        for f in futs:
            assert f.result() is not None

    pos = {row["name"]: row["cost"] for row in user_portfolio.load_positions(sid, path=p)}
    assert pos == {f"Item {i}": float(i + 1) for i in range(12)}


def test_lotes_manuais_separar_tirar_vendidas_e_juntar_sem_misturar_origem(tmp_path):
    p = tmp_path / "l.db"
    sid = "76561198000002222"
    pos = user_portfolio.add_position(sid, "AK-47", 10.0, 1, path=p)
    pos = user_portfolio.add_position(sid, "AK-47", 20.0, 2, path=p)
    assert pos[0].get("lote") and pos[1].get("lote")
    assert pos[0]["lote"] != pos[1]["lote"]

    # Editar só o segundo lote manual pelo id
    user_portfolio.update_position_cost(sid, "AK-47", 25.0, lote=pos[1]["lote"], path=p)
    atual = user_portfolio.load_positions(sid, path=p)
    assert [r["cost"] for r in atual] == [10.0, 25.0]

    # devolver_lote sem campo lote ganha um id novo
    user_portfolio.devolver_lote(sid, {"name": "AWP", "cost": 50.0, "quantity": 1, "source": "steam"}, path=p)
    awp = [r for r in user_portfolio.load_positions(sid, path=p) if r["name"] == "AWP"][0]
    assert awp.get("lote")

    # separar pula lote fora_desde e lote de 1 unidade para achar o lote elegível seguinte
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Caixa", "cost": 5.0, "quantity": 4, "source": "steam", "lote": "f1", "fora_desde": 100.0},
        {"name": "Caixa", "cost": 5.0, "quantity": 1, "source": "steam", "lote": "u1"},
        {"name": "Caixa", "cost": 5.0, "quantity": 3, "source": "steam", "lote": "u3"},
    ], path=p)
    novo_lote = user_portfolio.separar(sid, "Caixa", 1, path=p)
    assert novo_lote is not None
    caixas = user_portfolio.load_positions(sid, path=p)
    assert [(r["lote"], r["quantity"]) for r in caixas[:3]] == [("f1", 4), ("u1", 1), ("u3", 2)]
    assert caixas[3]["lote"] == novo_lote and caixas[3]["quantity"] == 1

    # tirar_vendidas pula linha sem custo / pequena e vende da linha elegível seguinte
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Skin", "cost": None, "quantity": 3, "source": "steam", "lote": "a", "fora_desde": 100.0},
        {"name": "Skin", "cost": 10.0, "quantity": 1, "source": "steam", "lote": "b", "fora_desde": 100.0},
        {"name": "Skin", "cost": 15.0, "quantity": 2, "source": "steam", "lote": "c", "fora_desde": 100.0},
    ], path=p)
    vendido = user_portfolio.tirar_vendidas(sid, "Skin", 2, path=p)
    assert vendido is not None and vendido["cost"] == 15.0 and vendido["lote"] == "c"

    # juntar recusa misturar lote steam + manual
    user_store.save_user_json(sid, "portfolio", [
        {"name": "Mista", "cost": 10.0, "quantity": 1, "source": "steam", "lote": "s1"},
        {"name": "Mista", "cost": 20.0, "quantity": 1, "source": "manual", "lote": "m1"},
    ], path=p)
    assert user_portfolio.juntar(sid, "Mista", path=p) == "nada"
    assert len(user_portfolio.load_positions(sid, path=p)) == 2


def test_inventario_sincronizar_nao_ressuscita_excluida_e_preserva_edicao_concorrente(tmp_path, monkeypatch):
    from lodout import steam_api
    p = tmp_path / "inv.db"
    monkeypatch.setattr("lodout.public_site.db._DB_PATH", p)
    sid_del = "76561198000003333"
    user_store.upsert_user(sid_del, persona_name="VaiSair", path=p)

    def _fetch_e_exclui(_sid):
        user_store.delete_user(sid_del, path=p)
        return (steam_api.INV_OK, [{"name": "AK-47", "quantity": 1}])

    monkeypatch.setattr(steam_api, "fetch_inventory", _fetch_e_exclui)
    inventario.sincronizar(sid_del)
    assert user_store.get_user(sid_del, path=p) is None
    assert user_portfolio.load_positions(sid_del, path=p) == []

    # Edição concorrente durante fetch_inventory não é sobrescrita pelo mesclar
    sid_race = "76561198000004444"
    user_store.upsert_user(sid_race, persona_name="Ativo", path=p)
    user_store.save_user_json(sid_race, "portfolio", [
        {"name": "AK-47", "cost": None, "quantity": 1, "source": "steam", "lote": "l1"},
    ], path=p)

    def _fetch_e_edita(_sid):
        user_portfolio.update_position_cost(sid_race, "AK-47", 77.5, lote="l1", path=p)
        return (steam_api.INV_OK, [{"name": "AK-47", "quantity": 1}])

    monkeypatch.setattr(steam_api, "fetch_inventory", _fetch_e_edita)
    inventario.sincronizar(sid_race)
    pos = user_portfolio.load_positions(sid_race, path=p)
    assert len(pos) == 1 and pos[0]["cost"] == 77.5


def test_sincronizar_em_segundo_plano_limpa_lock_se_thread_falhar(monkeypatch):
    sid = "76561198000005555"

    class _ThreadQuebrada:
        def __init__(self, *a, **k):
            pass

        def start(self):
            raise RuntimeError("sem threads")

    monkeypatch.setattr(inventario.threading, "Thread", _ThreadQuebrada)
    monkeypatch.setattr(inventario, "_gravar_estado", lambda *_a, **_k: None)
    with pytest.raises(RuntimeError):
        _SYNC_BG_REAL(sid)
    assert sid not in inventario._em_andamento


def test_atualizar_inventario_destrava_em_andamento_velho_e_meta_preserva_preferencias(client, monkeypatch):
    sid = "76561198000006666"
    token = _logar(client, sid)
    user_store.save_user_json(sid, "inventario_sync", {
        "em_andamento": True, "iniciado_ts": time.time() - 600, "ts": time.time() - 900,
    })
    disparos = []
    monkeypatch.setattr(inventario, "sincronizar_em_segundo_plano", lambda s: disparos.append(s) or True)
    r = client.post("/conta/inventario/atualizar", data={"csrf_token": token})
    assert r.status_code == 302
    assert disparos == [sid]

    # definir_meta preserva outras chaves de preferencias
    user_store.save_user_json(sid, "preferencias", {"recuperar_ignorar": ["Caixa A"]})
    r_meta = client.post("/conta/meta", data={"meta": "35", "csrf_token": token},
                         headers={"Accept": "application/json"})
    assert r_meta.status_code == 200 and r_meta.get_json() == {"ok": True, "meta": 35}
    prefs = user_store.load_user_json(sid, "preferencias", {})
    assert prefs["meta_lucro_pct"] == 35
    assert prefs["recuperar_ignorar"] == ["Caixa A"]


def test_migrar_trades_antigos_concorrente_nao_duplica_vendas(tmp_path):
    p = tmp_path / "tr.db"
    sid = "76561198000007777"
    user_store.save_user_json(sid, "trades", [
        {"name": "AK-47", "buy_cost": 10.0, "sell_price": 20.0, "quantity": 1, "ts": 1000.0},
        {"name": "M4A4", "buy_cost": 30.0, "sell_price": 45.0, "quantity": 2, "ts": 2000.0},
    ], path=p)

    barreira = threading.Barrier(4)

    def _rodar():
        barreira.wait()
        return user_trocas.migrar_trades_antigos(sid, path=p)

    with ThreadPoolExecutor(max_workers=4) as pool:
        contagens = list(pool.map(lambda _: _rodar(), range(4)))

    assert sum(contagens) == 2
    vendidos = user_vendidos.load(sid, path=p)
    assert len(vendidos) == 2
    assert {v["name"] for v in vendidos} == {"AK-47", "M4A4"}


def test_history_listar_carrega_vendidos_uma_unica_vez(client, monkeypatch):
    sid = "76561198000008888"
    _logar(client, sid)
    user_vendidos.adicionar(sid, "AK-47", 10.0, 20.0, 1)
    chamadas = 0
    real_load = user_vendidos.load

    def _espiao(*a, **k):
        nonlocal chamadas
        chamadas += 1
        return real_load(*a, **k)

    monkeypatch.setattr(user_vendidos, "load", _espiao)
    r = client.get("/conta/historico")
    assert r.status_code == 200
    assert chamadas == 1


# ── 3. Limites numéricos/comprimento e rotas <path:name> ──────────────

def test_limites_numericos_e_item_com_barra_em_conta_e_watchlist(client):
    sid = "76561198000009111"
    token = _logar(client, sid)

    # Overflow/limites rejeitados sem 500
    for payload in (
        {"name": "X" * 201, "cost": "10", "quantity": "1"},
        {"name": "Skin", "cost": "1e308", "quantity": "1"},
        {"name": "Skin", "cost": "1e309", "quantity": "1"},
        {"name": "Skin", "cost": "10", "quantity": "1" + "0" * 310},
        {"name": "Skin", "cost": "10", "quantity": "10001"},
    ):
        r = client.post("/conta/posicoes", data={**payload, "csrf_token": token})
        assert r.status_code == 302
    assert user_portfolio.load_positions(sid) == []

    # Item com "/" funciona em todas as ações da conta
    nome_barra = "Sticker | A/B (Holo)"
    client.post("/conta/posicoes", data={
        "name": nome_barra, "cost": "10,00", "quantity": "3", "csrf_token": token,
    })
    assert len(user_portfolio.load_positions(sid)) == 1

    # Custo acima do limite rejeitado em JSON (400)
    r_bad_cost = client.post(
        f"/conta/posicoes/{nome_barra}/custo",
        data={"cost": "99999999", "csrf_token": token},
        headers={"Accept": "application/json"},
    )
    assert r_bad_cost.status_code == 400

    # Editar custo, separar, juntar e remover funcionam com "/"
    r_ok = client.post(
        f"/conta/posicoes/{nome_barra}/custo",
        data={"cost": "15,00", "csrf_token": token},
        headers={"Accept": "application/json"},
    )
    assert r_ok.status_code == 200 and r_ok.get_json()["ok"] is True

    r_sep = client.post(f"/conta/posicoes/{nome_barra}/separar",
                        data={"quantidade": "1", "csrf_token": token})
    assert r_sep.status_code == 302
    lotes = user_portfolio.load_positions(sid)
    assert len(lotes) == 2
    client.post(f"/conta/posicoes/{nome_barra}/custo",
                data={"cost": "25,00", "lote": lotes[1]["lote"], "csrf_token": token})
    r_junt = client.post(f"/conta/posicoes/{nome_barra}/juntar", data={"csrf_token": token})
    assert r_junt.status_code == 302
    assert len(user_portfolio.load_positions(sid)) == 1

    r_rem = client.post(f"/conta/posicoes/{nome_barra}/remover", data={"csrf_token": token})
    assert r_rem.status_code == 302
    assert user_portfolio.load_positions(sid) == []

    # Watchlist: limites e item com "/"
    client.post("/conta/watchlist", data={"name": "Y" * 201, "target": "10", "csrf_token": token})
    client.post("/conta/watchlist", data={"name": "Skin", "target": "99999999", "csrf_token": token})
    assert user_watchlist.load_items(sid) == []

    client.post("/conta/watchlist", data={"name": nome_barra, "target": "20", "csrf_token": token})
    assert len(user_watchlist.load_items(sid)) == 1
    client.post(f"/conta/watchlist/{nome_barra}/regras",
                data={"price_below": "99999999", "csrf_token": token})
    assert user_watchlist.load_items(sid)[0].get("rules", {}).get("price_below") is None
    client.post(f"/conta/watchlist/{nome_barra}/regras",
                data={"price_below": "18,50", "baseline_price": "99999999", "csrf_token": token})
    assert user_watchlist.load_items(sid)[0].get("rules", {}).get("price_below") is None
    client.post(f"/conta/watchlist/{nome_barra}/regras",
                data={"price_below": "18,50", "csrf_token": token})
    assert user_watchlist.load_items(sid)[0]["rules"]["price_below"] == 18.5
    client.post(f"/conta/watchlist/{nome_barra}/remover", data={"csrf_token": token})
    assert user_watchlist.load_items(sid) == []


# ── 4. profile_fetcher hardening ──────────────────────────────────────

def test_profile_fetcher_allowlist_traversal_tamanho_e_cache_invalido(monkeypatch, tmp_path):
    avdir = tmp_path / "avatars"
    avdir.mkdir()
    monkeypatch.setattr(pf, "_AVATARS_DIR", avdir)
    monkeypatch.setattr(pf, "_PROFILES_PATH", tmp_path / "profiles.json")

    chamadas = []
    monkeypatch.setattr(pf, "_http_get", lambda url, timeout=15.0: (chamadas.append(url), b"ok")[1])

    # Host fora da allowlist ou HTTP sem TLS nunca dispara rede
    assert pf._download_avatar("7656", "https://example.com/a.jpg") is None
    assert pf._download_avatar("7656", "http://avatars.steamstatic.com/a.jpg") is None
    assert pf._download_avatar("7656", "https://evilsteamstatic.com/a.jpg") is None
    # Path traversal no steamid nunca dispara rede
    assert pf._download_avatar("../evil", "https://avatars.steamstatic.com/a.jpg") is None
    assert pf._download_avatar("a/b", "https://avatars.steamstatic.com/a.jpg") is None
    assert chamadas == []

    # Avatar acima de 2 MiB é recusado
    monkeypatch.setattr(pf, "_http_get", lambda url, timeout=15.0: b"x" * (pf._AVATAR_MAX_BYTES + 1))
    assert pf._download_avatar("7656", "https://avatars.fastly.steamstatic.com/big.jpg") is None
    assert not (avdir / "7656.jpg").exists()

    # Avatar válido grava atomicamente
    monkeypatch.setattr(pf, "_http_get", lambda url, timeout=15.0: b"\xff\xd8\xff\xd9")
    out = pf._download_avatar("7656", "https://avatars.akamaihd.net/ok.jpg")
    assert out == str(avdir / "7656.jpg")
    assert (avdir / "7656.jpg").read_bytes() == b"\xff\xd8\xff\xd9"

    # Cache JSON não-dict volta {}
    (tmp_path / "profiles.json").write_text("[]", encoding="utf-8")
    assert pf._load_cache() == {}


# ── 5. Estabilidade web, performance e qualidade de dados ─────────────

def test_latencia_thread_safe():
    latencia.reset()
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(latencia.registrar, f"ep{i % 4}", float(i)) for i in range(400)]
        futs += [pool.submit(latencia.resumo) for _ in range(40)]
        for f in futs:
            f.result()
    res = latencia.resumo()
    assert len(res) == 4
    assert sum(r["contagem"] for r in res) == 400
    latencia.reset()


def test_rate_limit_podar_remove_lote_de_10_por_cento(monkeypatch):
    rate_limit.reset()
    monkeypatch.setattr(rate_limit, "_MAX_CHAVES", 100)
    agora = 1_000_000.0
    for i in range(105):
        rate_limit.allow(f"k:{i}", 10, 60.0, now=agora + i * 0.01)
    assert len(rate_limit._hits) <= 95


def test_online_rejeita_quebra_de_linha_e_cria_indice():
    valido = "a" * 16
    assert online.id_valido(valido) is True
    assert online.id_valido(valido + "\n") is False
    online.marcar(valido, agora=1_000_000.0)
    conn = online._conectar()
    try:
        indices = [r[1] for r in conn.execute("PRAGMA index_list(presenca)").fetchall()]
    finally:
        conn.close()
    assert "idx_presenca_ts" in indices


def test_buscas_e_home_limitam_tamanho_e_tratam_zero_como_filtro(client, tmp_path, monkeypatch):
    p = tmp_path / "b.json"
    termo_longo = "a" * 200
    buscas.registrar(termo_longo, path=p)
    assert buscas.mais_buscados(path=p) == [("a" * 80, 1)]

    monkeypatch.setattr("lodout.scan_store.load_last_scan", lambda: {
        "ts": time.time(), "category": "Rifles", "results": [
            {"name": 'AK-47 | "Blueberry" (Field-Tested)', "score": 88, "price": 50.0,
             "case_label": "", "pump_risk": {"level": "low"}, "breakdown": []},
        ],
    })
    r_q = client.get("/?q=" + "z" * 300)
    assert r_q.status_code == 200
    assert ("z" * 120) in r_q.data.decode("utf-8")
    assert ("z" * 121) not in r_q.data.decode("utf-8")

    # preco_max=0 e nota_min=0 contam como filtro ativo (sem hero de destaque)
    r_zero = client.get("/?preco_max=0")
    assert r_zero.status_code == 200
    assert 'class="destaque-hero"' not in r_zero.data.decode("utf-8")

    # JSON-LD em /item com aspas no nome faz parse válido
    r_item = client.get('/item/AK-47%20%7C%20%22Blueberry%22%20(Field-Tested)')
    assert r_item.status_code == 200
    html = r_item.data.decode("utf-8")
    blocos = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    assert len(blocos) == 2
    parsed = [json.loads(b) for b in blocos]
    assert '"Blueberry"' in parsed[0]["name"]
    assert '"Blueberry"' in parsed[1]["itemListElement"][1]["name"]


def test_signals_cache_metricas_por_stat_e_invalida_na_escrita(tmp_path, monkeypatch):
    p = tmp_path / "vol.json"
    monkeypatch.setattr(signals, "_VOLUME_PATH", p)
    signals.record_item_volume("AK-47", 100)

    leituras = 0
    real_load = signals.load_json_record

    def _espiao(*a, **k):
        nonlocal leituras
        leituras += 1
        return real_load(*a, **k)

    monkeypatch.setattr(signals, "load_json_record", _espiao)
    h1 = signals.load_item_volume("AK-47")
    h2 = signals.load_item_volume("AK-47")
    assert leituras == 1
    assert len(h1) == 1 and h2[0]["value"] == 100.0
    # Mutar a cópia devolvida não contamina o cache
    h1.append({"ts": 0, "value": 999.0})
    assert len(signals.load_item_volume("AK-47")) == 1

    # Nova gravação invalida o cache
    signals.record_item_volume("AK-47", 250)
    h3 = signals.load_item_volume("AK-47")
    assert len(h3) == 2 and h3[-1]["value"] == 250.0


def test_notas_historico_ranking_consistente_peso_igual_por_dia_e_indice():
    dia = 86400.0
    # Meio-dia UTC (~09h Brasília) garante 4 coletas no mesmo dia de Brasília
    agora = 20_000 * dia + 18 * 3600
    # 8 dias de histórico: 7 dias antigos com 1 coleta/dia (nota 100) + 1 dia recente com 4 coletas (nota 20).
    # Média ponderada por coleta seria (7*100 + 4*20)/11 = 70.9;
    # Média ponderada por dia (igual para cada dia) é (7*100 + 20)/8 = 90.0.
    for d in range(8, 1, -1):
        ts = agora - d * dia
        notas_historico.gravar_snapshot(
            {"ts": ts, "items": [
                {"name": "Item Antigo Forte", "score": 100, "position": 1},
                {"name": "Item Constante", "score": 80, "position": 2},
            ]},
            agora=agora,
        )
    for h in (0, 2, 4, 6):
        ts = agora - h * 3600
        notas_historico.gravar_snapshot(
            {"ts": ts, "items": [
                {"name": "Item Antigo Forte", "score": 20, "position": 5},
                {"name": "Item Constante", "score": 80, "position": 1},
            ]},
            agora=agora,
        )

    res = notas_historico.ranking_consistente(30, agora=agora)
    assert res["modo"] == "media"
    por_nome = {it["name"]: it for it in res["itens"]}
    assert por_nome["Item Antigo Forte"]["media"] == 90.0
    assert por_nome["Item Constante"]["media"] == 80.0
    assert res["itens"][0]["name"] == "Item Antigo Forte"
    assert res["coletas"] == 11

    conn = notas_historico._conectar()
    try:
        indices = [r[1] for r in conn.execute("PRAGMA index_list(pontos)").fetchall()]
    finally:
        conn.close()
    assert "idx_pontos_completo_ts" in indices
