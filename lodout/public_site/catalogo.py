"""Catálogo amplo: todo o mercado de CS2 com o preço do dia, sem nota.

Plano: `plans/pending/catalogo-grande.md` (2026-11-14). O site dá nota a
~180 itens (precisa do histórico de cada um, 2 consultas por item). O
catálogo cobre o resto -- skins em todos os desgastes, caixas, cápsulas e
adesivos -- pela busca do Mercado da Steam, que traz até 100 itens por
consulta com menor preço, quantidade à venda, imagem, cor de raridade e
tipo. Quem visita acha qualquer item; a nota continua só onde há histórico.

Quem consulta a Steam é só o worker (`varrer`), no tempo livre entre as
rodadas, devagar e parando no primeiro bloqueio. O site só lê o SQLite.

Também concentra as regras de nome que o site e o catálogo dividem:
desgaste ("exterior"), versão (StatTrak™/Souvenir) e o texto de busca
(inglês + português, sem acento, com sinônimos).
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import unicodedata
from pathlib import Path

from lodout import _paths
from lodout.localization import localize_name

_logger = logging.getLogger(__name__)

# ── Regras de nome (compartilhadas com server.py) ────────────────────

# Valor curto na URL -> (texto no nome de mercado, rótulo no site).
EXTERIORES = {
    "fn": ("(Factory New)", "Nova de Fábrica"),
    "mw": ("(Minimal Wear)", "Pouco Usada"),
    "ft": ("(Field-Tested)", "Testada em Campo"),
    "ww": ("(Well-Worn)", "Bastante Usada"),
    "bs": ("(Battle-Scarred)", "Veterana de Guerra"),
}
VERSOES = {
    "normal": "Normal",
    "stattrak": "StatTrak™",
    "souvenir": "Souvenir",
}


def exterior_do_item(nome: str) -> "str | None":
    for chave, (sufixo, _rotulo) in EXTERIORES.items():
        if nome.endswith(sufixo):
            return chave
    return None


def versao_do_item(nome: str) -> str:
    if "StatTrak" in nome:
        return "stattrak"
    if nome.startswith("Souvenir "):
        return "souvenir"
    return "normal"


def texto_busca(texto: str) -> str:
    """Minúsculo, sem acento e sem hífen: "Cápsula" casa com "capsula" e
    "AK-47" com "ak47"."""
    sem_acento = "".join(
        ch for ch in unicodedata.normalize("NFKD", texto)
        if not unicodedata.combining(ch))
    return sem_acento.lower().replace("-", "")


# Palavras dos nomes em inglês que ficam sem tradução no site (cápsulas e
# adesivos aparecem com o nome original): quem digita em português também
# acha ("capsula copenhagen" -> "Copenhagen 2024 Legends Sticker Capsule").
SINONIMOS_BUSCA = {
    "capsule": "capsula",
    "sticker": "adesivo",
    "autograph": "autografo",
    "case": "caixa",
    "gloves": "luvas",
    "knife": "faca",
}


def nome_para_busca(nome_original: str, nome_pt: str) -> str:
    """Nome em português e original (inglês, como na Steam) juntos, mais
    a tradução das palavras de tipo que ficam em inglês no nome."""
    extras = [pt for en, pt in SINONIMOS_BUSCA.items()
              if en in nome_original.lower()]
    return " ".join([nome_pt, nome_original, *extras])


# ── Fatias da varredura ──────────────────────────────────────────────

# (rótulo, tag de tipo da Steam). A ordem é a da varredura: armas e
# facas/luvas primeiro, depois caixas/cápsulas, por último os adesivos
# (a fatia maior). Ordenadas por nome na Steam: paginação estável mesmo
# que a quantidade à venda mude no meio da varredura.
FATIAS = (
    ("Rifles", "CSGO_Type_Rifle"),
    ("Rifles de precisão", "CSGO_Type_SniperRifle"),
    ("Pistolas", "CSGO_Type_Pistol"),
    ("SMGs", "CSGO_Type_SMG"),
    ("Escopetas", "CSGO_Type_Shotgun"),
    ("Metralhadoras", "CSGO_Type_Machinegun"),
    ("Facas", "CSGO_Type_Knife"),
    ("Luvas", "Type_Hands"),
    ("Caixas e cápsulas", "CSGO_Type_WeaponCase"),
    ("Adesivos", "CSGO_Tool_Sticker"),
)


def categoria_do_item(fatia: str, nome: str) -> str:
    """Categoria do site para um item do catálogo (as mesmas abas)."""
    if fatia == "Rifles de precisão":
        return "Rifles"
    if fatia == "Caixas e cápsulas":
        if "Autograph" in nome:
            return "Cápsulas de autógrafo"
        if "Capsule" in nome:
            return "Cápsulas"
        return "Caixas"
    return fatia


def _raridade_do_item(nome: str, name_color: "str | None") -> str:
    # Mesma regra de raridade.py: faca/luva (★) é dourada mesmo com a cor
    # de Covert. Importado aqui dentro porque raridade.py importa o Flask.
    from lodout.public_site import raridade
    return raridade.raridade_suffix({
        "name_color": name_color,
        "quality_id": "unusual" if nome.startswith("★") else None,
    })


# ── Banco ────────────────────────────────────────────────────────────

def _caminho_banco() -> Path:
    return _paths.DATA_DIR / "catalogo.sqlite3"


def _caminho_estado() -> Path:
    return _paths.DATA_DIR / "catalogo_estado.json"


_ESQUEMA = """
CREATE TABLE IF NOT EXISTS itens (
    nome TEXT PRIMARY KEY,
    nome_pt TEXT NOT NULL,
    busca TEXT NOT NULL,
    preco REAL,
    a_venda INTEGER NOT NULL DEFAULT 0,
    categoria TEXT NOT NULL,
    raridade TEXT NOT NULL DEFAULT '',
    exterior TEXT,
    versao TEXT NOT NULL,
    icon TEXT,
    atualizado_em REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_itens_categoria ON itens (categoria);
CREATE INDEX IF NOT EXISTS idx_itens_a_venda ON itens (a_venda DESC);
"""


def conectar(caminho: "Path | None" = None) -> sqlite3.Connection:
    """Conexão com o banco do catálogo, criando o esquema se faltar.

    WAL: o site (outro processo) lê enquanto o worker grava."""
    caminho = caminho or _caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(caminho), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_ESQUEMA)
    return conn


def gravar(conn: sqlite3.Connection, fatia: str, itens: "list[dict]",
           agora: "float | None" = None) -> int:
    """Grava (insere ou atualiza) uma página da busca, numa transação."""
    agora = time.time() if agora is None else agora
    linhas = []
    for it in itens:
        nome = it.get("hash_name") or it.get("name")
        if not nome:
            continue
        nome_pt = localize_name(nome)
        linhas.append((
            nome, nome_pt, texto_busca(nome_para_busca(nome, nome_pt)),
            it.get("price"), int(it.get("listings") or 0),
            categoria_do_item(fatia, nome),
            _raridade_do_item(nome, it.get("name_color")),
            exterior_do_item(nome), versao_do_item(nome),
            it.get("icon"), agora,
        ))
    with conn:
        conn.executemany(
            """INSERT INTO itens (nome, nome_pt, busca, preco, a_venda,
                   categoria, raridade, exterior, versao, icon, atualizado_em)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(nome) DO UPDATE SET
                   nome_pt=excluded.nome_pt, busca=excluded.busca,
                   preco=excluded.preco, a_venda=excluded.a_venda,
                   categoria=excluded.categoria, raridade=excluded.raridade,
                   exterior=excluded.exterior, versao=excluded.versao,
                   icon=COALESCE(excluded.icon, itens.icon),
                   atualizado_em=excluded.atualizado_em""",
            linhas)
    return len(linhas)


def contar(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) FROM itens").fetchone()[0]


# ── Estado da varredura ──────────────────────────────────────────────

def ler_estado() -> dict:
    estado = _paths.load_json_record(_caminho_estado(), {})
    return estado if isinstance(estado, dict) else {}


def _salvar_estado(estado: dict) -> None:
    _paths.atomic_write_text(
        _caminho_estado(), json.dumps(estado, ensure_ascii=False))


# ── Varredura (só o worker chama) ────────────────────────────────────

# A busca da Steam é muito mais vigiada que as outras consultas (medido em
# 2026-07-28, ver discovery.py: dezenas de minutos de bloqueio depois de
# poucas dezenas de chamadas seguidas). Por isso a pausa entre páginas é um
# múltiplo de `steam_api.RATE_LIMIT_DELAY_S`, lido na hora de cada pausa.
_FATOR_PAUSA_PADRAO = 5.0
# Depois de um bloqueio, a varredura não volta antes disto, mesmo que o
# disjuntor da Steam já tenha liberado (sem retry logo depois de 429).
_ESPERA_APOS_BLOQUEIO_S = 2 * 3600
# 1 rodada completa por dia (decisão do usuário, 2026-11-15): a busca sem
# login devolve 10 itens por página, não 100 -- o mercado inteiro são
# ~2.700 páginas, ~15 h no ritmo atual (0 bloqueio em 365 páginas
# seguidas). A cada 6 h não cabe.
_INTERVALO_RODADA_H_PADRAO = 24.0


def ligado() -> bool:
    from lodout._ambiente import ambiente
    return (ambiente("CATALOGO") or "").strip().lower() in ("1", "true", "sim")


def _fator_pausa() -> float:
    from lodout._ambiente import ambiente
    try:
        return max(1.0, float(ambiente("CATALOGO_FATOR_PAUSA",
                                       str(_FATOR_PAUSA_PADRAO))))
    except (TypeError, ValueError):
        return _FATOR_PAUSA_PADRAO


def _intervalo_rodada_s() -> float:
    from lodout._ambiente import ambiente
    try:
        horas = float(ambiente("CATALOGO_INTERVALO_HORAS",
                               str(_INTERVALO_RODADA_H_PADRAO)))
    except (TypeError, ValueError):
        horas = _INTERVALO_RODADA_H_PADRAO
    return max(1.0, horas) * 3600


def _dormir(segundos: float, ate_ts: float, deve_parar) -> bool:
    """Dorme em passos curtos. False se a janela acabou ou mandaram parar."""
    fim = min(time.time() + segundos, ate_ts)
    while time.time() < fim:
        if deve_parar():
            return False
        time.sleep(min(1.0, max(0.0, fim - time.time())))
    return time.time() < ate_ts and not deve_parar()


def varrer(ate_ts: float, deve_parar=lambda: False) -> dict:
    """Avança a varredura do catálogo até `ate_ts` e devolve o estado.

    Continua de onde parou (fatia + posição ficam em
    `data/catalogo_estado.json`). Uma rodada nova só começa quando a
    última completa tem mais de `CATALOGO_INTERVALO_HORAS` (padrão 24 h).
    Para no primeiro bloqueio (429), em erro, em página vazia antes do
    fim (pode ser bloqueio silencioso) e quando a janela acaba."""
    from lodout import steam_api

    estado = ler_estado()
    agora = time.time()
    ultimo_bloqueio = float(estado.get("ultimo_bloqueio_ts") or 0)
    if agora - ultimo_bloqueio < _ESPERA_APOS_BLOQUEIO_S:
        estado["motivo"] = "esperando_apos_bloqueio"
        return estado
    if steam_api.em_cooldown("search"):
        estado["motivo"] = "cooldown"
        return estado
    if estado.get("fatia") is None:
        ultima = float(estado.get("ultima_completa_ts") or 0)
        if agora - ultima < _intervalo_rodada_s():
            estado["motivo"] = "em_dia"
            return estado
        estado.update({
            "fatia": 0, "start": 0, "inicio_ts": agora,
            "paginas_rodada": 0, "itens_rodada": 0, "totais": {},
        })

    conn = conectar()
    motivo = "janela"
    try:
        while True:
            if deve_parar() or time.time() >= ate_ts:
                break
            nome_fatia, tag = FATIAS[estado["fatia"]]
            status, pagina, total = steam_api.search_market(
                facets={"type": tag}, sort="name", descending=False,
                start=int(estado["start"]), count=100)
            estado["paginas_rodada"] = int(estado.get("paginas_rodada") or 0) + 1
            estado["paginas_total"] = int(estado.get("paginas_total") or 0) + 1
            estado["ultima_pagina_ts"] = time.time()
            if status == steam_api.SEARCH_RATE_LIMITED:
                estado["bloqueios"] = int(estado.get("bloqueios") or 0) + 1
                estado["ultimo_bloqueio_ts"] = time.time()
                motivo = "bloqueio"
                _logger.warning("Catálogo: bloqueio (429) em %s, posição %s",
                                nome_fatia, estado["start"])
                break
            if status != steam_api.SEARCH_OK:
                estado["erros"] = int(estado.get("erros") or 0) + 1
                motivo = "erro"
                break
            estado.setdefault("totais", {})[nome_fatia] = total
            if not pagina and int(estado["start"]) < total:
                # Página vazia antes do fim: pode ser bloqueio silencioso
                # (AGENTS.md). Não avança; tenta de novo na próxima janela.
                estado["vazias"] = int(estado.get("vazias") or 0) + 1
                motivo = "pagina_vazia"
                break
            estado["itens_rodada"] = (int(estado.get("itens_rodada") or 0)
                                      + gravar(conn, nome_fatia, pagina))
            if pagina:
                estado["tamanho_pagina"] = len(pagina)
            estado["start"] = int(estado["start"]) + len(pagina)
            if not pagina or estado["start"] >= total:
                estado["fatia"] = int(estado["fatia"]) + 1
                estado["start"] = 0
                if estado["fatia"] >= len(FATIAS):
                    fim = time.time()
                    estado.update({
                        "fatia": None, "ultima_completa_ts": fim,
                        "duracao_ultima_min": round(
                            (fim - float(estado.get("inicio_ts") or fim)) / 60, 1),
                        "itens_ultima": estado.get("itens_rodada"),
                        "paginas_ultima": estado.get("paginas_rodada"),
                    })
                    motivo = "completa"
                    _logger.info("Catálogo completo: %s itens em %s páginas",
                                 estado["itens_ultima"], estado["paginas_ultima"])
                    break
            _salvar_estado(estado)
            pausa = steam_api.RATE_LIMIT_DELAY_S * _fator_pausa()
            if not _dormir(pausa, ate_ts, deve_parar):
                break
        estado["itens_no_banco"] = contar(conn)
    finally:
        conn.close()
        estado["motivo"] = motivo
        _salvar_estado(estado)
    return estado


def resumo() -> dict:
    """O que o /api/health mostra do catálogo (só leitura, sem rede)."""
    estado = ler_estado()
    chaves = ("fatia", "start", "paginas_rodada", "itens_rodada",
              "ultima_completa_ts", "duracao_ultima_min", "itens_ultima",
              "paginas_ultima", "tamanho_pagina", "bloqueios",
              "ultimo_bloqueio_ts", "erros", "vazias", "itens_no_banco",
              "totais", "motivo", "ultima_pagina_ts")
    return {k: estado.get(k) for k in chaves if k in estado}


# ── Leitura (o site) ─────────────────────────────────────────────────
# Só SQLite local: nenhuma consulta à Steam. Sem banco (dev, testes, ou
# antes da 1a varredura), tudo volta vazio e o site segue como antes.

def _conectar_leitura() -> "sqlite3.Connection | None":
    caminho = _caminho_banco()
    if not caminho.exists():
        return None
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def _where(filtros: dict, excluir: "list[str]") -> "tuple[str, list]":
    """Cláusula WHERE para os filtros da busca (mesma regra de busca do
    site: palavras em qualquer ordem, sem acento; "a OR b")."""
    partes, args = [], []
    busca = (filtros.get("busca") or "").strip()
    if busca:
        grupos = []
        for grupo in texto_busca(busca).split(" or "):
            palavras = [p for p in grupo.split() if any(ch.isalnum() for ch in p)]
            if palavras:
                grupos.append("(" + " AND ".join("busca LIKE ?" for _ in palavras) + ")")
                args.extend(f"%{p}%" for p in palavras)
        if grupos:
            partes.append("(" + " OR ".join(grupos) + ")")
    for coluna, chave in (("categoria", "categoria"), ("exterior", "exterior"),
                          ("raridade", "raridade"), ("versao", "versao")):
        if filtros.get(chave):
            partes.append(f"{coluna} = ?")
            args.append(filtros[chave])
    if filtros.get("preco_max") is not None:
        partes.append("preco <= ?")
        args.append(float(filtros["preco_max"]))
    partes.append("preco IS NOT NULL")
    if excluir:
        partes.append(f"nome NOT IN ({','.join('?' * len(excluir))})")
        args.extend(excluir)
    return " AND ".join(partes), args


def consultar(filtros: dict, excluir: "list[str]" = (), ordenar: str = "a_venda",
              limite: int = 12, offset: int = 0) -> "tuple[int, list[dict]]":
    """(total, itens) do catálogo que batem com os filtros, sem os
    `excluir` (os itens com nota, que a lista já mostra antes)."""
    conn = _conectar_leitura()
    if conn is None:
        return 0, []
    try:
        where, args = _where(filtros, list(excluir))
        total = conn.execute(f"SELECT COUNT(*) FROM itens WHERE {where}",
                             args).fetchone()[0]
        ordem = "preco ASC" if ordenar == "preco" else "a_venda DESC, nome"
        linhas = conn.execute(
            f"SELECT * FROM itens WHERE {where} ORDER BY {ordem} "
            "LIMIT ? OFFSET ?", [*args, max(0, int(limite)), max(0, int(offset))]
        ).fetchall() if limite > 0 else []
        return total, [dict(r) for r in linhas]
    except sqlite3.Error:
        _logger.warning("leitura do catálogo falhou", exc_info=True)
        return 0, []
    finally:
        conn.close()


def contar_por_categoria(filtros: dict, excluir: "list[str]" = ()) -> dict:
    conn = _conectar_leitura()
    if conn is None:
        return {}
    try:
        where, args = _where({**filtros, "categoria": None}, list(excluir))
        return {r[0]: r[1] for r in conn.execute(
            f"SELECT categoria, COUNT(*) FROM itens WHERE {where} "
            "GROUP BY categoria", args)}
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def item(nome: str) -> "dict | None":
    conn = _conectar_leitura()
    if conn is None:
        return None
    try:
        r = conn.execute("SELECT * FROM itens WHERE nome = ?", (nome,)).fetchone()
        return dict(r) if r else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def precos(nomes: "list[str]") -> "dict[str, float]":
    """{nome: preço do dia} para os nomes que o catálogo tem."""
    nomes = [n for n in nomes if n]
    conn = _conectar_leitura()
    if conn is None or not nomes:
        if conn is not None:
            conn.close()
        return {}
    try:
        out = {}
        for i in range(0, len(nomes), 500):
            lote = nomes[i:i + 500]
            for r in conn.execute(
                    f"SELECT nome, preco FROM itens WHERE nome IN "
                    f"({','.join('?' * len(lote))}) AND preco IS NOT NULL", lote):
                out[r[0]] = r[1]
        return out
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


def tem_dados() -> bool:
    conn = _conectar_leitura()
    if conn is None:
        return False
    try:
        return conn.execute("SELECT 1 FROM itens LIMIT 1").fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        conn.close()
