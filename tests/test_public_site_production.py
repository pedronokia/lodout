"""Testes do endurecimento de produção (Fase 3) e infraestrutura de deploy."""
from __future__ import annotations

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest
from flask import Flask

from lodout.public_site import server
from lodout.public_site.wsgi import app as wsgi_app

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _carregar_script(nome: str):
    caminho = _REPO_ROOT / "scripts" / nome
    spec = importlib.util.spec_from_file_location(nome.removesuffix(".py"), caminho)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_wsgi_app_e_flask_app():
    assert isinstance(wsgi_app, Flask)


def test_secure_cookie_desligado_por_padrao(monkeypatch):
    monkeypatch.delenv("LODOUT_PUBLIC_SITE_SECURE_COOKIES", raising=False)
    app = server.create_app()
    assert app.config["SESSION_COOKIE_SECURE"] is False


def test_secure_cookie_ligado_via_env(monkeypatch):
    monkeypatch.setenv("LODOUT_PUBLIC_SITE_SECURE_COOKIES", "1")
    app = server.create_app()
    assert app.config["SESSION_COOKIE_SECURE"] is True


def test_cookie_httponly_e_samesite_sempre_ligados():
    app = server.create_app()
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    assert app.config["SESSION_COOKIE_SAMESITE"] == "Lax"


def test_proxy_fix_aplicado():
    from werkzeug.middleware.proxy_fix import ProxyFix
    app = server.create_app()
    assert isinstance(app.wsgi_app, ProxyFix)


def test_build_id_prefere_variavel_de_ambiente(monkeypatch, tmp_path):
    arquivo = tmp_path / "BUILD_ID"
    arquivo.write_text("20261119-000000\n", encoding="utf-8")
    monkeypatch.setattr(server, "_BUILD_ID_PATH", arquivo)

    monkeypatch.delenv("LODOUT_BUILD_ID", raising=False)
    assert server._build_id() == "20261119-000000"

    monkeypatch.setenv("LODOUT_BUILD_ID", "20261120-163000-abc1234")
    assert server._build_id() == "20261120-163000-abc1234"


def test_entrypoint_sintaxe_valida_e_sem_chown_incondicional():
    ep = _REPO_ROOT / "entrypoint.sh"
    res = subprocess.run(["sh", "-n", str(ep)], capture_output=True, text=True)
    assert res.returncode == 0, res.stderr
    conteudo = ep.read_text(encoding="utf-8")
    assert "stat -c '%u:%g' /data" in conteudo
    assert "find /data -maxdepth 1" in conteudo


def test_compose_sem_duplicacao_de_volumes_no_override():
    base = (_REPO_ROOT / "docker-compose.public-site.yml").read_text(encoding="utf-8")
    oracle = (_REPO_ROOT / "docker-compose.oracle.yml").read_text(encoding="utf-8")

    assert "./lodout:/app/lodout:ro" in base
    assert "LODOUT_BUILD_ID=${LODOUT_BUILD_ID:-}" in base
    assert "./lodout:/app/lodout:ro" not in oracle
    assert "skinvault_data:/data" not in oracle


def test_deploy_workflow_endurecido():
    wf = (_REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in wf
    assert "timeout-minutes: 15" in wf
    assert "workflow_dispatch:" in wf

    # GitHub Actions não permite `secrets.*` dentro de `if:`.
    for linha in wf.splitlines():
        if linha.lstrip().startswith("if:"):
            assert "secrets." not in linha

    # Extrai cada bloco `script: |` dos passos SSH e garante boas práticas.
    blocos_script = re.findall(
        r"          script: \|\n((?:            .*\n|\n)+)", wf
    )
    assert len(blocos_script) == 3
    for script in blocos_script:
        assert "set -euo pipefail" in script
        assert "${{ secrets." not in script

    assert "envs: SITE_DOMAIN,ADMIN_DISCORD_WEBHOOK,ADMIN_PASSWORD,RESTART_CADDY,FORCE_REBUILD" in wf
    assert "envs: SITE_DOMAIN,ADMIN_DISCORD_WEBHOOK,ADMIN_PASSWORD\n" in wf
    assert "envs: SITE_DOMAIN,ADMIN_DISCORD_WEBHOOK,ADMIN_PASSWORD,FORCE_REBUILD" in wf
    assert "docker image prune -f --filter \"until=168h\" || true" in wf
    assert "docker builder prune -f --filter \"until=168h\" || true" in wf
    assert ".lodout-web-build.sha256" in wf
    assert ".lodout-worker-build.sha256" in wf
    assert ".lodout-prev-sha" in wf
    assert "failure() && steps.deploy_web.outcome == 'success'" in wf
    assert "/readyz" in wf
    assert "scripts/smoke_test.py" in wf


class _FlaskSmokeAdapter:
    """Adapta `app.test_client()` à interface mínima de `httpx.Client.get`
    sem acionar rede (conftest bloqueia `httpx.Client`)."""

    def __init__(self, app: Flask) -> None:
        self._client = app.test_client()

    def get(self, url: str, follow_redirects: bool = False):
        caminho = url.split("http://testserver", 1)[-1]
        resp = self._client.get(caminho, follow_redirects=follow_redirects)

        class _Resp:
            status_code = resp.status_code
            headers = resp.headers

            @staticmethod
            def json():
                data = resp.get_json(silent=True)
                if data is None:
                    raise ValueError("resposta não é JSON")
                return data

        return _Resp()


@pytest.mark.parametrize("admin_hash", ["", "pbkdf2:sha256:1$sal$hash"])
def test_smoke_test_passa_contra_app_real(monkeypatch, admin_hash):
    smoke = _carregar_script("smoke_test.py")
    monkeypatch.setattr(server, "_ADMIN_PASSWORD_HASH", admin_hash)
    app = server.create_app()
    falhas, total = smoke.verificar_site(
        "http://testserver", client=_FlaskSmokeAdapter(app)
    )
    assert falhas == 0
    assert total == len(smoke._ROTAS) + 1


def test_smoke_test_falha_se_admin_abrir_sem_login():
    smoke = _carregar_script("smoke_test.py")

    class _AdminAberto:
        def get(self, _url: str, follow_redirects: bool = False):
            class _Resp:
                status_code = 200
                headers: dict[str, str] = {}

            return _Resp()

    assert smoke._verificar_admin_protegido(_AdminAberto(), "http://testserver") is False


def test_check_env_drift_por_servico():
    drift = _carregar_script("check_env_drift.py")
    assert drift.verificar_env("web", env={"LODOUT_DATA_DIR": "/data"}) == []
    assert drift.verificar_env("web", env={}) == ["LODOUT_DATA_DIR"]
    assert drift.verificar_env("caddy", env={"SITE_DOMAIN": "lodout.com"}) == []
    assert drift.verificar_env("caddy", env={}) == ["SITE_DOMAIN"]
    assert drift.verificar_env("todos", env={}) == ["SITE_DOMAIN", "LODOUT_DATA_DIR"]


def test_dockerfile_gunicorn_tem_flags_de_estabilidade():
    df = (_REPO_ROOT / "Dockerfile.public-site").read_text(encoding="utf-8")
    assert "--timeout 60" in df
    assert "--graceful-timeout 30" in df
    assert "--max-requests 1000" in df
    assert "--max-requests-jitter 100" in df


def test_compose_tem_healthcheck_limites_e_hardening():
    base = (_REPO_ROOT / "docker-compose.public-site.yml").read_text(encoding="utf-8")
    oracle = (_REPO_ROOT / "docker-compose.oracle.yml").read_text(encoding="utf-8")

    assert "healthcheck:" in base
    assert "http://127.0.0.1:8000/readyz" in base
    assert "init: true" in base
    assert "mem_limit: 512m" in base
    assert "pids_limit: 128" in base
    assert "stop_grace_period: 35s" in base

    assert "no-new-privileges:true" in oracle
    assert "condition: service_healthy" in oracle
    assert "mem_limit: 256m" in oracle


def test_db_connect_configura_pragmas_e_reinicializa_se_arquivo_recriado(tmp_path):
    from lodout.public_site import db

    caminho = tmp_path / "teste_site.db"
    conn = db.connect(caminho)
    try:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "user_data"}.issubset(tabelas)
    finally:
        conn.close()

    # Segunda conexão no mesmo arquivo usa caminho rápido e mantém pragmas por conexão.
    conn2 = db.connect(caminho)
    try:
        assert conn2.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
        assert conn2.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        conn2.close()

    # Se o arquivo for apagado e recriado no mesmo caminho, o schema volta automaticamente.
    for suf in ("", "-wal", "-shm"):
        Path(str(caminho) + suf).unlink(missing_ok=True)
    conn3 = db.connect(caminho)
    try:
        tabelas = {r[0] for r in conn3.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"users", "user_data"}.issubset(tabelas)
    finally:
        conn3.close()


def test_check_site_health_detecta_falhas_e_valida_webhook():
    hc = _carregar_script("check_site_health.py")

    def _ok(url: str):
        if url.endswith("/readyz"):
            return 200, {"ready": True}, None
        return 200, {
            "ok": True,
            "intervalo_horas_configurado": 6.0,
            "scan": {"disponivel": True, "idade_segundos": 3600.0},
        }, None

    assert hc.verificar_saude("https://lodout.com", fetcher=_ok) == []

    def _atrasado_e_sem_db(url: str):
        if url.endswith("/readyz"):
            return 503, {"ready": False, "motivos": ["banco: locked"]}, None
        return 200, {
            "ok": True,
            "intervalo_horas_configurado": 6.0,
            "scan": {"disponivel": True, "idade_segundos": 20 * 3600.0},
        }, None

    problemas = hc.verificar_saude("https://lodout.com", fetcher=_atrasado_e_sem_db)
    assert len(problemas) == 2
    assert any("/readyz" in p for p in problemas)
    assert any("scan atrasado" in p for p in problemas)

    assert hc.enviar_alerta_discord("https://evil.example/hook", "teste") is False


def test_workflows_de_monitoramento_endurecidos():
    for nome in ("health-check.yml", "tls-check.yml"):
        wf = (_REPO_ROOT / ".github" / "workflows" / nome).read_text(encoding="utf-8")
        assert "permissions:\n  contents: read" in wf
        assert "timeout-minutes: 5" in wf
        assert "set -euo pipefail" in wf


def test_caddyfile_endurecido():
    cf = (_REPO_ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "-Server" in cf
    assert 'Cross-Origin-Opener-Policy "same-origin-allow-popups"' in cf
    assert "@dotfiles" in cf
    assert "not path /.well-known/*" in cf
    assert "respond @dotfiles 404" in cf


def test_icon_cache_limpar_antigos(tmp_path):
    import os
    from lodout.public_site import icon_cache

    agora = 1_800_000_000.0
    pasta = tmp_path / "icon_cache"
    pasta.mkdir()

    # v3 já substituído por v4 -> deve sair mesmo sendo recente
    v3_subst = pasta / "abc.v3.192.webp"
    v4_atual = pasta / "abc.v4.192.webp"
    v3_subst.write_bytes(b"v3")
    v4_atual.write_bytes(b"v4")
    os.utime(v3_subst, (agora - 100, agora - 100))
    os.utime(v4_atual, (agora - 50, agora - 50))

    # v3 recente SEM v4 -> deve ficar como fallback
    v3_reserva = pasta / "def.v3.192.webp"
    v3_reserva.write_bytes(b"v3-only")
    os.utime(v3_reserva, (agora - 3600, agora - 3600))

    # legado antigo (>30 dias) -> deve sair
    legado_velho = pasta / "old.jpg"
    legado_velho.write_bytes(b"jpg")
    os.utime(legado_velho, (agora - 40 * 86400, agora - 40 * 86400))

    # 3 v4 extras para testar o teto max_arquivos=2
    for idx in range(3):
        p = pasta / f"item{idx}.v4.192.webp"
        p.write_bytes(b"v4")
        ts = agora - (500 - idx * 100)
        os.utime(p, (ts, ts))

    removidos = icon_cache.limpar_antigos(
        cache_dir=pasta, max_arquivos=2, dias_legado=30, now=agora
    )
    # Removeu: v3_subst (1) + legado_velho (1) + 2 v4 mais antigos (2) = 4
    assert removidos == 4
    assert not v3_subst.exists()
    assert not legado_velho.exists()
    assert v3_reserva.exists()
    assert len(list(pasta.glob("*.v4.*.webp"))) == 2
    assert v4_atual.exists()


def test_sqlite_pragmas_notas_online_e_catalogo():
    from lodout.public_site import catalogo, notas_historico, online

    conn_n = notas_historico._conectar()
    try:
        assert conn_n.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn_n.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
        assert conn_n.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        conn_n.close()

    conn_o = online._conectar()
    try:
        assert conn_o.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn_o.execute("PRAGMA busy_timeout").fetchone()[0] >= 2000
        assert conn_o.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        conn_o.close()

    conn_cw = catalogo.conectar()
    try:
        assert conn_cw.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert conn_cw.execute("PRAGMA busy_timeout").fetchone()[0] >= 10000
        assert conn_cw.execute("PRAGMA synchronous").fetchone()[0] == 1
    finally:
        conn_cw.close()

    conn_cr = catalogo._conectar_leitura()
    assert conn_cr is not None
    try:
        assert conn_cr.execute("PRAGMA busy_timeout").fetchone()[0] >= 5000
        assert conn_cr.execute("PRAGMA query_only").fetchone()[0] == 1
    finally:
        conn_cr.close()


def test_disco_info_inclui_catalogo_notas_e_icones():
    info = server._disco_info()
    for chave in ("livre_fmt", "total_fmt", "db_fmt", "backups_fmt",
                  "catalogo_fmt", "notas_fmt", "icones_fmt"):
        assert chave in info
        assert isinstance(info[chave], str)


