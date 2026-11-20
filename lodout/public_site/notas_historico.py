"""Histórico da nota de cada item, para 90 dias e 1 ano (pedido 17/11).

O `rankings.json` guarda as últimas 150 fotos do ranking (~37 dias) e é
relido inteiro a cada página: não serve para um ano. Aqui cada foto vira
linhas (item, hora, nota, posição) num SQLite próprio:

- as fotos dos últimos `DIAS_COMPLETOS` ficam inteiras (4 por dia);
- mais velhas, fica a última foto de cada dia (a mesma hora para todos
  os itens, então ainda dá para remontar o Top 20 daquele dia);
- mais velhas que `DIAS_MAX`, apagadas.

`completo`: 1 nas fotos com TODOS os itens (gravadas pelo worker desde
17/11); 0 nas importadas do rankings.json, que só têm o Top 20. O
gráfico de um item usa só as completas (uma foto só do Top 20 mostraria
o item apenas nos dias em que ele estava lá); a comparação do Ranking
usa as duas.

Só o worker grava (a cada coleta completa, junto com `ranking.save_
snapshot`); as páginas só leem. Na primeira gravação, as fotos que já
estavam no `rankings.json` entram aqui (o histórico começa no dia em que
o site entrou no ar: não há como recuperar notas de antes).
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import time
from pathlib import Path

from lodout import _paths

_logger = logging.getLogger(__name__)
_INIT_LOCK = threading.Lock()
_INICIALIZADOS: set[tuple[str, int, int]] = set()

DIAS_COMPLETOS = 35
DIAS_MAX = 400
_FUSO_BR_S = -3 * 3600  # dia de calendário de Brasília para a compactação


def _caminho() -> Path:
    return Path(_paths.DATA_DIR) / "notas_historico.sqlite3"


def _chave_arquivo(p: Path) -> "tuple[str, int, int] | None":
    try:
        st = p.stat()
    except OSError:
        return None
    if st.st_size == 0:
        return None
    return (str(p.resolve()), st.st_dev, st.st_ino)


def _conectar() -> sqlite3.Connection:
    p = _caminho()
    p.parent.mkdir(parents=True, exist_ok=True)
    chave = _chave_arquivo(p)
    conn = sqlite3.connect(str(p), timeout=5)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    if chave is None or chave not in _INICIALIZADOS:
        with _INIT_LOCK:
            if chave is None or chave not in _INICIALIZADOS:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""CREATE TABLE IF NOT EXISTS pontos (
                    name TEXT NOT NULL, ts REAL NOT NULL, score INTEGER NOT NULL,
                    position INTEGER, completo INTEGER NOT NULL DEFAULT 1,
                    PRIMARY KEY (name, ts))""")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_pontos_ts ON pontos (ts)")
                conn.commit()
                nova_chave = _chave_arquivo(p)
                if nova_chave is not None:
                    _INICIALIZADOS.add(nova_chave)
    return conn


def _inserir(conn: sqlite3.Connection, snapshot: dict, completo: int = 1) -> int:
    ts = float(snapshot.get("ts") or 0)
    linhas = [(it["name"], ts, int(it.get("score") or 0), it.get("position"), completo)
              for it in snapshot.get("items") or [] if it.get("name")]
    conn.executemany("INSERT OR REPLACE INTO pontos (name, ts, score, position, completo) "
                     "VALUES (?, ?, ?, ?, ?)", linhas)
    return len(linhas)


def _importar_rankings_json(conn: sqlite3.Connection) -> int:
    from lodout import ranking
    n = 0
    for snap in ranking.load_snapshots():
        if isinstance(snap, dict) and snap.get("ts"):
            n += _inserir(conn, snap, completo=0)
    return n


def compactar(conn: sqlite3.Connection, agora: float) -> None:
    corte = agora - DIAS_COMPLETOS * 86400
    # Mantém, por dia de Brasília, só a última foto (a mesma hora para
    # todos os itens daquele dia).
    conn.execute("""
        DELETE FROM pontos WHERE ts < :corte AND ts NOT IN (
            SELECT MAX(ts) FROM pontos WHERE ts < :corte
            GROUP BY CAST((ts + :fuso) / 86400 AS INTEGER))""",
                 {"corte": corte, "fuso": _FUSO_BR_S})
    conn.execute("DELETE FROM pontos WHERE ts < ?", (agora - DIAS_MAX * 86400,))


def gravar_snapshot(snapshot: dict, agora: "float | None" = None) -> None:
    """Worker: grava uma foto do ranking (e, na primeira vez, as do
    rankings.json). Nunca derruba a coleta: erro vira aviso no log."""
    agora = time.time() if agora is None else agora
    try:
        novo = not _caminho().exists()
        conn = _conectar()
        try:
            with conn:
                if novo or not conn.execute("SELECT 1 FROM pontos LIMIT 1").fetchone():
                    _importar_rankings_json(conn)
                _inserir(conn, snapshot)
                compactar(conn, agora)
        finally:
            conn.close()
    except Exception:
        _logger.warning("histórico da nota: gravação falhou", exc_info=True)


def _garantir_importado() -> None:
    """Antes da 1ª coleta depois do deploy, o banco não existe: a página
    cria e copia as fotos do rankings.json (idempotente)."""
    if _caminho().exists():
        return
    try:
        conn = _conectar()
        try:
            with conn:
                _importar_rankings_json(conn)
        finally:
            conn.close()
    except Exception:
        _logger.warning("histórico da nota: importação falhou", exc_info=True)


def _ler(sql: str, args: tuple) -> list:
    _garantir_importado()
    if not _caminho().exists():
        return []
    try:
        conn = _conectar()
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        _logger.warning("histórico da nota: leitura falhou", exc_info=True)
        return []


def serie(name: str, dias: float, agora: "float | None" = None) -> "list[dict]":
    """[{ts, score}] do item nos últimos `dias`, do mais antigo ao mais novo."""
    agora = time.time() if agora is None else agora
    return [{"ts": ts, "score": score} for ts, score in _ler(
        "SELECT ts, score FROM pontos WHERE name = ? AND ts >= ? AND completo = 1 ORDER BY ts",
        (name, agora - dias * 86400))]


def primeiro_ts_completo() -> "float | None":
    """Desde quando há nota de todos os itens (início do gráfico do item)."""
    linha = _ler("SELECT MIN(ts) FROM pontos WHERE completo = 1", ())
    return linha[0][0] if linha and linha[0][0] else None


def snapshot_ate(ts_alvo: float) -> "dict | None":
    """A foto mais recente até `ts_alvo`, no formato do rankings.json
    ({ts, items: [{name, score, position}]}). None se não há tão antiga."""
    linha = _ler("SELECT MAX(ts) FROM pontos WHERE ts <= ?", (ts_alvo,))
    ts = linha[0][0] if linha else None
    if not ts:
        return None
    itens = _ler("SELECT name, score, position FROM pontos WHERE ts = ? "
                 "ORDER BY position", (ts,))
    return {"ts": ts, "items": [{"name": n, "score": s, "position": p}
                                for n, s, p in itens]}


# ── Ranking "os melhores de forma consistente" (pedido 17/11) ─────────
# Quem quer comprar procura o que SE MANTÉM bem avaliado, não o que bateu
# 100 numa coleta (parte da nota vem de retratos do livro de ofertas, que
# oscilam muito). O /ranking ordena pela nota média no período.
MIN_DIAS_COMPLETOS = 7     # com menos histórico completo que isso, usa a presença no Top 20
MIN_PRESENCA = 0.5         # item precisa aparecer em metade das coletas do período


def ranking_consistente(dias: float, agora: "float | None" = None, top: int = 20) -> dict:
    """{"modo": "media"|"presenca"|None, "itens": [...], "coletas": n,
    "desde": ts}. Cada item: name, valor (nota média, ou % das coletas no
    Top 20), media, presenca_pct, dias_no_top.

    "media": quando há pelo menos `MIN_DIAS_COMPLETOS` dias de fotos com
    todos os itens; média das notas no período, só para quem aparece em
    pelo menos `MIN_PRESENCA` das coletas (item recém-chegado não entra
    com 2 pontos). "presenca": antes disso, % das coletas do período em
    que o item esteve no Top 20 (dado que existe desde o lançamento),
    desempate pela média da nota nessas vezes."""
    agora = time.time() if agora is None else agora
    desde = agora - dias * 86400
    inicio_completo = primeiro_ts_completo()
    dias_completos = (agora - inicio_completo) / 86400 if inicio_completo else 0
    fuso = _FUSO_BR_S
    dias_top = {n: d for n, d in _ler(
        "SELECT name, COUNT(DISTINCT CAST((ts + ?) / 86400 AS INTEGER)) FROM pontos "
        "WHERE ts >= ? AND position <= 20 GROUP BY name", (fuso, desde))}
    if dias_completos >= MIN_DIAS_COMPLETOS:
        desde_media = max(desde, inicio_completo)
        coletas = (_ler("SELECT COUNT(DISTINCT ts) FROM pontos WHERE completo = 1 AND ts >= ?",
                        (desde_media,)) or [(0,)])[0][0]
        linhas = _ler("SELECT name, AVG(score), COUNT(*) FROM pontos WHERE completo = 1 AND ts >= ? "
                      "GROUP BY name", (desde_media,))
        itens = [{"name": n, "valor": round(m, 1), "media": round(m, 1),
                  "presenca_pct": round(100 * c / coletas) if coletas else 0,
                  "dias_no_top": dias_top.get(n, 0)}
                 for n, m, c in linhas if coletas and c >= MIN_PRESENCA * coletas]
        itens.sort(key=lambda i: (-i["media"], -i["dias_no_top"], i["name"]))
        return {"modo": "media", "itens": itens[:top], "coletas": coletas, "desde": desde_media}
    coletas = (_ler("SELECT COUNT(DISTINCT ts) FROM pontos WHERE ts >= ?", (desde,)) or [(0,)])[0][0]
    linhas = _ler("SELECT name, COUNT(DISTINCT ts), AVG(score) FROM pontos "
                  "WHERE ts >= ? AND position <= 20 GROUP BY name", (desde,))
    if not coletas or not linhas:
        return {"modo": None, "itens": [], "coletas": coletas, "desde": desde}
    itens = [{"name": n, "valor": round(100 * c / coletas), "media": round(m, 1),
              "presenca_pct": round(100 * c / coletas), "dias_no_top": dias_top.get(n, 0)}
             for n, c, m in linhas]
    itens.sort(key=lambda i: (-i["presenca_pct"], -i["media"], i["name"]))
    primeiro = (_ler("SELECT MIN(ts) FROM pontos WHERE ts >= ?", (desde,)) or [(None,)])[0][0]
    return {"modo": "presenca", "itens": itens[:top], "coletas": coletas, "desde": primeiro or desde}
