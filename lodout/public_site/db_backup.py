"""Backup rotativo dos bancos SQLite e JSONs globais do site -- local
primeiro, "pra fora da VM" é responsabilidade de quem opera (ver README:
baixar via scp periodicamente). Protege contra corrupção/bug de aplicação,
não contra perda da VM inteira -- isso precisaria de um destino externo
(S3 etc.) que exigiria credenciais que não temos como configurar sozinhos.

Usa a API de backup do próprio sqlite3 (não um `shutil.copy` cru) --
segura mesmo com o banco sendo escrito ao mesmo tempo por outro processo
(o `web`), sem lock nem corrupção de leitura parcial.
"""
from __future__ import annotations

import calendar
import sqlite3
import time
import zipfile
from pathlib import Path

from lodout import _paths
from lodout._paths import DATA_DIR

_DB_PATH = DATA_DIR / "public_site.db"
_BACKUP_DIR = DATA_DIR / "backups"
_MANTER = 7  # backups diários -- cobre uma semana de histórico
_INTERVALO_MIN_S = 20 * 3600  # não faz 2 backups no mesmo dia

# JSON globais do dashboard -- achado da 2a rodada (2026-10-25): só o
# SQLite (conta/portfolio pessoal) tinha backup; perder `scanner_last`/
# `rankings` sem isso significa perder o scan atual e o histórico de
# ciclos num crash de disco, sem nenhum jeito de recuperar sem esperar
# o próximo ciclo (que pode levar horas se a Steam estiver bloqueando).
_JSON_PATHS = {
    "scanner_last": DATA_DIR / "scanner_last.json",
    "scan_historico": DATA_DIR / "scan_historico.json",
    "rankings": DATA_DIR / "rankings.json",
}


def _timestamp_do_nome(caminho: Path, prefixo: str) -> float:
    """Hora embutida no NOME do arquivo (não `stat().st_mtime`, que é
    hora real do SO e não o `now` injetável do teste -- gotcha já
    documentado aqui mesmo, ver `fazer_backup_se_necessario`)."""
    ts_texto = caminho.stem.removeprefix(prefixo)
    try:
        # timegm (não mktime): o nome é gerado com gmtime (UTC).
        return calendar.timegm(time.strptime(ts_texto, "%Y%m%d-%H%M%S"))
    except ValueError:
        return caminho.stat().st_mtime


def _deve_pular(existentes: list[Path], prefixo: str, agora: float) -> bool:
    if not existentes:
        return False
    return (agora - _timestamp_do_nome(existentes[-1], prefixo)) < _INTERVALO_MIN_S


def _backup_sqlite_rotativo(
        src: Path,
        dest_dir: Path,
        prefixo: str,
        extensao: str,
        agora: float) -> "Path | None":
    """Copia `src` via API `sqlite3.Connection.backup()` com rotação de
    `_MANTER` arquivos e limpeza do destino parcial em caso de falha."""
    if not src.exists():
        return None
    padrao = f"{prefixo}*{extensao}"
    existentes = sorted(dest_dir.glob(padrao)) if dest_dir.exists() else []
    if _deve_pular(existentes, prefixo, agora):
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    nome = time.strftime(f"{prefixo}%Y%m%d-%H%M%S{extensao}", time.gmtime(agora))
    destino = dest_dir / nome
    origem_conn = None
    destino_conn = None
    try:
        origem_conn = sqlite3.connect(str(src), timeout=10.0)
        destino_conn = sqlite3.connect(str(destino), timeout=10.0)
        with destino_conn:
            origem_conn.backup(destino_conn)
        check = destino_conn.execute("PRAGMA quick_check").fetchone()
        if not check or check[0] != "ok":
            raise sqlite3.DatabaseError(f"quick_check falhou: {check}")
    except sqlite3.Error:
        if destino_conn is not None:
            destino_conn.close()
            destino_conn = None
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass
        return None
    finally:
        if origem_conn is not None:
            origem_conn.close()
        if destino_conn is not None:
            destino_conn.close()

    todos = sorted(dest_dir.glob(padrao))
    for antigo in todos[:-_MANTER]:
        try:
            antigo.unlink()
        except OSError:
            pass
    return destino


def fazer_backup_se_necessario(
        db_path: "Path | str | None" = None,
        backup_dir: "Path | str | None" = None,
        now: "float | None" = None) -> "Path | None":
    """Faz backup de `public_site.db` se o mais recente já existente tem
    mais de ~20h (ou não existe nenhum). Devolve o path criado, ou None
    se pulou/falhou."""
    src = Path(db_path) if db_path is not None else _DB_PATH
    dest_dir = Path(backup_dir) if backup_dir is not None else _BACKUP_DIR
    agora = time.time() if now is None else now
    return _backup_sqlite_rotativo(src, dest_dir, "public_site-", ".db", agora)


def fazer_backup_notas_se_necessario(
        db_path: "Path | str | None" = None,
        backup_dir: "Path | str | None" = None,
        now: "float | None" = None) -> "Path | None":
    """Mesma cadência (1x/~20h, guarda os últimos `_MANTER`) para
    `notas_historico.sqlite3` -- guarda até 400 dias de histórico de
    notas que não podem ser reconstruídos a partir da Steam."""
    src = (Path(db_path) if db_path is not None
           else Path(_paths.DATA_DIR) / "notas_historico.sqlite3")
    dest_dir = Path(backup_dir) if backup_dir is not None else _BACKUP_DIR
    agora = time.time() if now is None else now
    return _backup_sqlite_rotativo(
        src, dest_dir, "notas_historico-", ".sqlite3", agora)


def fazer_backup_json_se_necessario(
        paths: "dict[str, Path] | None" = None,
        backup_dir: "Path | str | None" = None,
        now: "float | None" = None) -> "Path | None":
    """Mesma cadência do backup do banco (1x/~20h, guarda os últimos
    `_MANTER`), pros JSON globais do dashboard (`_JSON_PATHS`) -- um
    .zip só por rodada, pra não multiplicar arquivo solto em
    `backups/`. None se nenhuma fonte existe, se já tem backup recente,
    ou se falhar gravando."""
    fontes = paths if paths is not None else _JSON_PATHS
    dest_dir = Path(backup_dir) if backup_dir is not None else _BACKUP_DIR
    agora = time.time() if now is None else now

    if not any(Path(p).exists() for p in fontes.values()):
        return None

    existentes = sorted(dest_dir.glob("json-*.zip")) if dest_dir.exists() else []
    if _deve_pular(existentes, "json-", agora):
        return None

    dest_dir.mkdir(parents=True, exist_ok=True)
    nome = time.strftime("json-%Y%m%d-%H%M%S.zip", time.gmtime(agora))
    destino = dest_dir / nome
    try:
        with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED) as zf:
            for nome_arq, p in fontes.items():
                p = Path(p)
                if p.exists():
                    zf.write(p, arcname=f"{nome_arq}.json")
    except OSError:
        try:
            destino.unlink(missing_ok=True)
        except OSError:
            pass
        return None

    todos = sorted(dest_dir.glob("json-*.zip"))
    for antigo in todos[:-_MANTER]:
        try:
            antigo.unlink()
        except OSError:
            pass
    return destino
