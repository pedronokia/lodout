"""Testes do endurecimento de produção (Fase 3) e infraestrutura de deploy."""
from __future__ import annotations

import importlib.util
import re
import shutil
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


@pytest.mark.skipif(
    shutil.which("sh") is None,
    reason="entrypoint.sh é validado com `sh -n`; sem sh (Windows) não há como rodar a checagem. A CI Linux continua executando.",
)
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
    assert "--control-socket /tmp/gunicorn.ctl" in df


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


def test_429_envia_cabecalho_retry_after():
    from lodout.public_site import rate_limit

    app = server.create_app()
    client = app.test_client()
    for _ in range(rate_limit.API_MAX_HITS):
        client.get("/api/recommendations")
    resp = client.get("/api/recommendations")
    assert resp.status_code == 429
    assert resp.headers.get("Retry-After") == "60"


def test_admin_lista_e_baixa_backups_de_notas_e_json(monkeypatch, tmp_path):
    from werkzeug.security import generate_password_hash

    (tmp_path / "notas_historico-20261120-120000.sqlite3").write_bytes(b"notas-bytes")
    (tmp_path / "json-20261120-120000.zip").write_bytes(b"zip-bytes")
    (tmp_path / "intruso.txt").write_bytes(b"nao-listar")

    monkeypatch.setattr(server, "_ADMIN_PASSWORD_HASH", generate_password_hash("segredo-123456"))
    monkeypatch.setattr(server.db_backup, "_BACKUP_DIR", tmp_path)
    app = server.create_app()
    client = app.test_client()
    client.post("/admin/login", data={"senha": "segredo-123456"})

    body = client.get("/admin").data.decode("utf-8")
    assert "notas_historico-20261120-120000.sqlite3" in body
    assert "json-20261120-120000.zip" in body
    assert "intruso.txt" not in body

    r1 = client.get("/admin/backup/notas_historico-20261120-120000.sqlite3")
    assert r1.status_code == 200 and r1.data == b"notas-bytes"
    r2 = client.get("/admin/backup/json-20261120-120000.zip")
    assert r2.status_code == 200 and r2.data == b"zip-bytes"
    assert client.get("/admin/backup/intruso.txt").status_code == 404


def test_readyz_falha_quando_notas_historico_corrompido(monkeypatch, tmp_path):
    from lodout.public_site import notas_historico

    corrompido = tmp_path / "notas_historico.sqlite3"
    corrompido.write_bytes(b"nao e sqlite")
    monkeypatch.setattr(notas_historico, "_caminho", lambda: corrompido)
    app = server.create_app()
    resp = app.test_client().get("/readyz")
    assert resp.status_code == 503
    dados = resp.get_json()
    assert dados["ready"] is False
    assert any(m.startswith("notas:") for m in dados["motivos"])


def test_dependabot_configurado_para_pip_docker_e_actions():
    dep = (_REPO_ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8")
    assert 'package-ecosystem: "pip"' in dep
    assert 'package-ecosystem: "docker"' in dep
    assert 'package-ecosystem: "github-actions"' in dep


def test_max_content_length_rejeita_post_gigante_com_413(monkeypatch):
    from werkzeug.security import generate_password_hash

    monkeypatch.setattr(server, "_ADMIN_PASSWORD_HASH", generate_password_hash("segredo-123456"))
    app = server.create_app()
    assert app.config["MAX_CONTENT_LENGTH"] == 256 * 1024
    client = app.test_client()
    payload_gigante = b"x" * (300 * 1024)

    r_api = client.post("/api/online", data=payload_gigante, content_type="application/json")
    assert r_api.status_code == 413
    assert r_api.get_json()["erro"] == "corpo_grande_demais"

    r_html = client.post("/admin/login", data={"senha": payload_gigante.decode("ascii")})
    assert r_html.status_code == 413


@pytest.mark.skipif(
    importlib.util.find_spec("fcntl") is None,
    reason="worker._lock_instancia usa fcntl, inexistente no Windows; a CI Linux continua executando.",
)
def test_worker_lock_instancia_bloqueia_segunda_instancia(tmp_path):
    from lodout.public_site import worker

    lock_file = tmp_path / "worker.lock"
    with worker._lock_instancia(lock_file):
        assert lock_file.exists()
        with pytest.raises(RuntimeError, match="outro worker"):
            with worker._lock_instancia(lock_file):
                pass
    # Após liberar, uma nova instância consegue adquirir normalmente.
    with worker._lock_instancia(lock_file):
        assert lock_file.read_text(encoding="utf-8").strip().isdigit()


def test_worker_manutencao_pos_ciclo_checkpoint_e_temps(tmp_path):
    import os
    from lodout.public_site import db, worker

    conn = db.connect(tmp_path / "public_site.db")
    conn.close()
    stale_tmp = tmp_path / "scanner_last.json.abc123.tmp"
    stale_tmp.write_text("parcial", encoding="utf-8")
    velho = 1_000_000.0
    os.utime(stale_tmp, (velho, velho))

    res = worker._manutencao_pos_ciclo(tmp_path)
    assert res["checkpoints"] == 1
    assert res["temps_removidos"] >= 1
    assert not stale_tmp.exists()


def test_visits_e_buscas_concorrentes_nao_perdem_contagem(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from lodout.public_site import buscas, visits

    visitas_path = tmp_path / "visitas.json"
    buscas_path = tmp_path / "buscas.json"

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [
            pool.submit(visits.registrar, visitas_path, 1_800_000_000.0)
            for _ in range(20)
        ] + [
            pool.submit(buscas.registrar, "ak-47", buscas_path)
            for _ in range(20)
        ]
        for f in futs:
            f.result()

    assert visits.total(visitas_path) == 20
    assert buscas.mais_buscados(limite=5, path=buscas_path) == [("ak-47", 20)]


def test_backup_offsite_empacota_cifra_e_decifra_roundtrip(tmp_path):
    import shutil
    import tarfile

    bo = _carregar_script("backup_offsite.py")
    backups = tmp_path / "backups"
    backups.mkdir()
    (backups / "public_site-20261119-030000.db").write_bytes(b"antigo")
    (backups / "public_site-20261120-030000.db").write_bytes(b"novo-db")
    (backups / "notas_historico-20261120-030000.sqlite3").write_bytes(b"novo-notas")
    (backups / "json-20261120-030000.zip").write_bytes(b"novo-json")
    (backups / "ignorar.txt").write_bytes(b"nao-entra")

    escolhidos = bo.selecionar_mais_recentes(backups)
    assert [p.name for p in escolhidos] == [
        "public_site-20261120-030000.db",
        "notas_historico-20261120-030000.sqlite3",
        "json-20261120-030000.zip",
    ]

    tar_orig = bo.criar_pacote_tar_gz(escolhidos, tmp_path / "orig.tar.gz")
    if shutil.which("openssl"):
        with pytest.raises(ValueError):
            bo.cifrar_arquivo(tar_orig, tmp_path / "x.enc", "curta")
        enc = bo.cifrar_arquivo(tar_orig, tmp_path / "backup.tar.gz.enc", "senha-super-segura-123")
        assert enc.read_bytes() != tar_orig.read_bytes()
        dec = bo.decifrar_arquivo(enc, tmp_path / "restaurado.tar.gz", "senha-super-segura-123")
        with tarfile.open(dec, "r:gz") as tf:
            assert sorted(tf.getnames()) == [
                "json-20261120-030000.zip",
                "notas_historico-20261120-030000.sqlite3",
                "public_site-20261120-030000.db",
            ]
            assert tf.extractfile("public_site-20261120-030000.db").read() == b"novo-db"

    with pytest.raises(ValueError):
        bo.enviar_http_put(tar_orig, "http://inseguro.example/o/")


def test_backup_offsite_workflow_endurecido():
    wf = (_REPO_ROOT / ".github" / "workflows" / "backup-offsite.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: read" in wf
    assert "timeout-minutes: 10" in wf
    assert "envs: BACKUP_UPLOAD_URL,BACKUP_PASSPHRASE" in wf
    assert "set -euo pipefail" in wf
    assert "trap 'rm -rf \"$TMPDIR\"' EXIT" in wf
    for linha in wf.splitlines():
        if linha.lstrip().startswith("if:"):
            assert "secrets." not in linha





