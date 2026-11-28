"""Testes do monitoramento de contas SteamID no painel /admin."""
from __future__ import annotations

import json
import sqlite3

from werkzeug.security import generate_password_hash

from lodout.public_site import db, server, user_store


def _criar_db_teste(tmp_path):
    p = tmp_path / "public_site.db"
    conn = db.connect(p)
    conn.close()
    return p


def test_resumo_usuarios_admin_sem_banco(tmp_path):
    res = server._resumo_usuarios_admin(path=tmp_path / "inexistente.db")
    assert res["total"] == 0
    assert res["ativos_7d"] == 0
    assert res["contas"] == []
    assert res["ultimo_login_txt"] is None
    assert res["grafico_novos"] == ""


def test_resumo_usuarios_admin_banco_corrompido(tmp_path):
    p = tmp_path / "corrupt.db"
    p.write_text("nao e sqlite", encoding="utf-8")
    res = server._resumo_usuarios_admin(path=p)
    assert res["total"] == 0
    assert res["contas"] == []


def test_resumo_usuarios_admin_metricas_e_ordenacao(tmp_path):
    p = _criar_db_teste(tmp_path)
    agora = 1_795_900_000.0
    conn = sqlite3.connect(str(p))
    try:
        conn.executemany(
            "INSERT INTO users (steamid, persona_name, avatar_url, created_ts, last_login_ts) "
            "VALUES (?, ?, ?, ?, ?)",
            [
                # Nova hoje e ativa agora
                ("76561198000000001", "Alice", None, agora - 3600, agora - 600),
                # Criada há 5 dias, ativa há 3 dias
                ("76561198000000002", "Bob", None, agora - 5 * 86400, agora - 3 * 86400),
                # Criada há 20 dias, ativa há 15 dias
                ("76561198000000003", None, None, agora - 20 * 86400, agora - 15 * 86400),
                # Antiga (>30d) e inativa (>30d), steamid não-numérico defensivo
                ("nao-numerico", "Legado", None, agora - 45 * 86400, agora - 40 * 86400),
            ],
        )
        conn.executemany(
            "INSERT INTO user_data (steamid, kind, payload, updated_ts) VALUES (?, ?, ?, ?)",
            [
                ("76561198000000001", "portfolio", json.dumps([{"name": "AK"}, {"name": "AWP"}]), agora),
                ("76561198000000001", "watchlist", json.dumps([{"name": "M4A4"}]), agora),
                ("76561198000000001", "webhook", json.dumps({"url": "https://discord.com/api/webhooks/1/a"}), agora),
                ("76561198000000002", "portfolio", json.dumps([{"name": "Caixa"}]), agora),
                ("76561198000000002", "watchlist", json.dumps([]), agora),
                # JSON quebrado não pode quebrar o painel
                ("76561198000000003", "portfolio", "{quebrado", agora),
                # Dado órfão de conta excluída não entra na contagem
                ("76561198999999999", "portfolio", json.dumps([{"name": "Orfao"}]), agora),
            ],
        )
        conn.commit()
    finally:
        conn.close()

    res = server._resumo_usuarios_admin(path=p, now=agora, limite=2)
    assert res["total"] == 4
    assert res["ativos_24h"] == 1
    assert res["ativos_7d"] == 2
    assert res["ativos_30d"] == 3
    assert res["novos_24h"] == 1
    assert res["novos_7d"] == 2
    assert res["novos_30d"] == 3
    assert res["com_portfolio"] == 2
    assert res["com_watchlist"] == 1
    assert res["com_webhook"] == 1
    assert res["ultimo_login_txt"] is not None
    assert "<svg" in res["grafico_novos"]
    assert res["exibidas"] == 2
    assert [c["steamid"] for c in res["contas"]] == ["76561198000000001", "76561198000000002"]
    alice = res["contas"][0]
    assert alice["nome"] == "Alice"
    assert alice["perfil_url"] == "https://steamcommunity.com/profiles/76561198000000001"
    assert alice["itens_portfolio"] == 2
    assert alice["tem_watchlist"] is True
    assert alice["tem_webhook"] is True
    assert "2 itens" in alice["uso_resumo"]
    assert "alertas" in alice["uso_resumo"]
    assert "Discord" in alice["uso_resumo"]

    # Sem limite apertado, verifica fallback de nome e steamid não-numérico sem link
    res_all = server._resumo_usuarios_admin(path=p, now=agora, limite=50)
    by_sid = {c["steamid"]: c for c in res_all["contas"]}
    assert by_sid["76561198000000003"]["nome"] == "Sem nome"
    assert by_sid["nao-numerico"]["perfil_url"] is None


def test_admin_renderiza_monitoramento_steamid_e_escapa_nome(tmp_path, monkeypatch):
    p = _criar_db_teste(tmp_path)
    user_store.upsert_user("76561198123456789", persona_name='<script>alert(1)</script>', path=p)
    user_store.save_user_json("76561198123456789", "portfolio", [{"name": "AK-47 | Redline"}], path=p)

    monkeypatch.setattr("lodout.public_site.server.db_backup._DB_PATH", p)
    monkeypatch.setattr(
        "lodout.public_site.server._ADMIN_PASSWORD_HASH",
        generate_password_hash("senha-admin-segura"),
    )

    app = server.create_app()
    client = app.test_client()
    assert client.post("/admin/login", data={"senha": "senha-admin-segura"}).status_code == 302

    resp = client.get("/admin")
    assert resp.status_code == 200
    assert resp.headers.get("Cache-Control") == "private, no-store"
    body = resp.data.decode("utf-8")
    assert "Contas com login Steam" in body
    assert "76561198123456789" in body
    assert "https://steamcommunity.com/profiles/76561198123456789" in body
    assert 'rel="noopener noreferrer"' in body
    assert "1 item" in body
    assert "<script>alert(1)</script>" not in body
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
