"""Catálogo amplo: todo o mercado de CS2 com o preço do dia, sem nota.

Plano: `plans/archive/catalogo-grande.md` (2026-11-14). O site dá nota a
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
import re
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
    "ww": ("(Well-Worn)", "Bem Desgastada"),
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
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
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
_SOBREPOSICAO = 1
# 404 na busca nao e' bloqueio (429), mas repetir a mesma posicao para
# sempre travava a rodada (25/11: start=2664 em Rifles). Depois destas
# tentativas no MESMO start, a fatia e' encerrada e as proximas andam.
_MAX_404_MESMO_START = 3
# Uma rodada em que fatias foram puladas por 404 NAO e' completa (25/11:
# 10 fatias puladas e o estado marcava "completa" com 2960 itens). Nao renova
# ultima_completa_ts e só tenta de novo depois desta espera, pra nao queimar
# requisicoes a cada ciclo do worker enquanto a Steam devolver 404.
_ESPERA_APOS_404_S = 24 * 3600
# A rodada seguinte recomeça na PRIMEIRA fatia pulada, no start em que ela
# falhou (26/11): refazer Rifles inteiro custava ~22 h e deixava as outras
# fatias sem volta. `fatias_puladas` guarda as 20 últimas só pra diagnóstico.
_MAX_FATIAS_PULADAS = 20


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


def _proxima_fatia(estado: dict) -> bool:
    """Passa para a proxima fatia. True se a rodada terminou."""
    estado["fatia"] = int(estado["fatia"]) + 1
    estado["start"] = 0
    estado["erro_404_seguidos"] = 0
    estado["erro_404_start"] = -1
    if estado["fatia"] < len(FATIAS):
        return False
    estado["fatia"] = None
    return True


def _finalizar_rodada(estado: dict) -> str:
    """Fecha a rodada sem fingir que foi completa quando houve 404.

    `ultima_completa_ts` continua com a última volta REAL: é o que o alerta
    de 72h usa. Uma rodada pulada por 404 registra `fim_ultima_rodada_ts`
    e `itens_ultima`, mas não renova o relógio da volta completa.
    """
    fim = time.time()
    puladas = int(estado.get("erros_404_fatias_rodada") or 0)
    estado.update({
        "fatia": None,
        "fim_ultima_rodada_ts": fim,
        "duracao_ultima_min": round(
            (fim - float(estado.get("inicio_ts") or fim)) / 60, 1),
        "itens_ultima": estado.get("itens_rodada"),
        "paginas_ultima": estado.get("paginas_rodada"),
    })
    if puladas:
        _logger.warning(
            "Catálogo: rodada terminou com %s fatia(s) pulada(s) por 404 "
            "(%s itens); não conta como volta completa",
            puladas, estado["itens_ultima"])
        # `retomar` aponta a PRIMEIRA fatia pulada desta rodada. Ela fica
        # no estado até uma rodada sem puladas (26/11): sem isso a volta
        # seguinte recomeçava em Rifles e gastava ~22 h antes de chegar
        # nas categorias que realmente faltaram.
        puladas_info = estado.get("fatias_puladas")
        estado["retomar"] = (puladas_info[0]
                             if isinstance(puladas_info, list) and puladas_info
                             else None)
        return "incompleta_404"
    estado["retomar"] = None
    estado["fatias_puladas"] = []
    estado["ultima_completa_ts"] = fim
    _logger.info("Catálogo completo: %s itens em %s páginas",
                 estado["itens_ultima"], estado["paginas_ultima"])
    return "completa"


def _dormir(segundos: float, ate_ts: float, deve_parar) -> bool:
    """Dorme em passos curtos. False se a janela acabou ou mandaram parar."""
    fim = min(time.time() + segundos, ate_ts)
    while time.time() < fim:
        if deve_parar():
            return False
        time.sleep(min(1.0, max(0.0, fim - time.time())))
    return time.time() < ate_ts and not deve_parar()


def _retomar_legado(estado: dict) -> "dict | None":
    """Recupera um ponto de retomada de estados gravados antes de 26/11.

    Na rodada de 24-25/11 as 10 fatias foram puladas por 404 e o estado
    antigo não guardava qual era o `start` da falha. `totais` diz quais
    fatias chegaram a responder: recomeçar no `total` da primeira delas
    pula as páginas já coletadas sem refazer a varredura inteira. Se a
    Steam devolver 200 vazio (ou 404) nessa posição, o laço normal já
    avança para a próxima fatia.
    """
    if (estado.get("motivo") != "incompleta_404"
            or not int(estado.get("erros_404_fatias_rodada") or 0)):
        return None
    totais = estado.get("totais")
    if not isinstance(totais, dict):
        return None
    for indice, (nome, tag) in enumerate(FATIAS):
        if nome not in totais:
            continue
        try:
            start = max(0, int(totais[nome]))
        except (TypeError, ValueError):
            continue
        return {"fatia": indice, "nome": nome, "tag": tag, "start": start,
                "ts": float(estado.get("fim_ultima_rodada_ts") or 0),
                "origem": "legado"}
    return None


def varrer(ate_ts: float, deve_parar=lambda: False) -> dict:
    """Avança a varredura do catálogo até `ate_ts` e devolve o estado.

    Continua de onde parou (fatia + posição ficam em
    `data/catalogo_estado.json`). Uma rodada nova só começa quando a
    última completa tem mais de `CATALOGO_INTERVALO_HORAS` (padrão 24 h).
    Para no primeiro bloqueio (429), em erro, em página vazia antes do
    fim (pode ser bloqueio silencioso) e quando a janela acaba. Fatias
    encerradas por 404 não contam como volta completa (nem renovam o
    relógio dela) e só são tentadas de novo após `_ESPERA_APOS_404_S`.
    A rodada seguinte retoma na primeira fatia pulada, no `start` da falha,
    em vez de recomeçar do zero (`retomar`/`fatias_puladas` no estado)."""
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
        if (estado.get("motivo") == "incompleta_404"
                and agora - float(estado.get("fim_ultima_rodada_ts") or 0)
                < _ESPERA_APOS_404_S):
            estado["motivo"] = "esperando_apos_404"
            return estado
        retomar = estado.get("retomar")
        if not isinstance(retomar, dict):
            retomar = _retomar_legado(estado)
            if retomar is not None:
                estado["retomar"] = retomar
        indice = 0
        inicio = 0
        if isinstance(retomar, dict):
            try:
                candidato = int(retomar.get("fatia"))
                if 0 <= candidato < len(FATIAS):
                    indice = candidato
                    inicio = max(0, int(retomar.get("start") or 0))
            except (TypeError, ValueError):
                pass
        estado.update({
            "fatia": indice, "start": inicio, "inicio_ts": agora,
            "paginas_rodada": 0, "itens_rodada": 0, "totais": {},
            "erro_404_seguidos": 0, "erro_404_start": -1,
            "erros_404_fatias": int(estado.get("erros_404_fatias") or 0),
            "erros_404_fatias_rodada": 0,
            "fatias_puladas": [],
        })
        if indice or inicio:
            _logger.info("Catálogo: retomando na fatia %s (%s) a partir de %s",
                         indice, FATIAS[indice][0], inicio)

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
            if status == steam_api.SEARCH_NOT_FOUND:
                atual = int(estado["start"])
                seguidos = (int(estado.get("erro_404_seguidos") or 0) + 1
                            if int(estado.get("erro_404_start", -1)) == atual
                            else 1)
                estado["erro_404_seguidos"] = seguidos
                estado["erro_404_start"] = atual
                estado["erros"] = int(estado.get("erros") or 0) + 1
                motivo = "erro_404"
                if seguidos >= _MAX_404_MESMO_START:
                    _logger.warning(
                        "Catálogo: %s 404 seguidos em %s na posição %s; "
                        "encerrando a fatia para não travar as próximas",
                        seguidos, nome_fatia, atual)
                    estado["erros_404_fatias"] = (
                        int(estado.get("erros_404_fatias") or 0) + 1)
                    estado["erros_404_fatias_rodada"] = (
                        int(estado.get("erros_404_fatias_rodada") or 0) + 1)
                    # Guarda QUAL fatia/tag/start falhou, não só quantas:
                    # sem isso a próxima rodada não sabe onde retomar (26/11).
                    totais = estado.get("totais")
                    total_fatia = (int(totais.get(nome_fatia) or 0)
                                   if isinstance(totais, dict) else 0)
                    pulada = {"fatia": int(estado["fatia"]), "nome": nome_fatia,
                              "tag": tag, "start": atual, "total": total_fatia,
                              "detalhe_404": steam_api.ultimo_404_busca(),
                              "ts": round(time.time(), 3)}
                    historico = estado.setdefault("fatias_puladas", [])
                    if not isinstance(historico, list):
                        historico = estado["fatias_puladas"] = []
                    historico.append(pulada)
                    if len(historico) > _MAX_FATIAS_PULADAS:
                        del historico[:-_MAX_FATIAS_PULADAS]
                    if len(historico) == 1:
                        estado["retomar"] = dict(pulada)
                    if _proxima_fatia(estado):
                        motivo = _finalizar_rodada(estado)
                        break
                else:
                    _logger.warning(
                        "Catálogo: 404 em %s na posição %s (%s/%s)",
                        nome_fatia, atual, seguidos, _MAX_404_MESMO_START)
                # Não para aqui: depois da pausa tenta de novo (ou já segue
                # com a próxima fatia se o limite de 404 foi atingido).
            elif status != steam_api.SEARCH_OK:
                estado["erros"] = int(estado.get("erros") or 0) + 1
                motivo = "erro"
                break
            else:
                estado["erro_404_seguidos"] = 0
                estado["erro_404_start"] = -1
                # Preserva o total conhecido mesmo se a página vier vazia:
                # é o que permite retomar a fatia sem refazê-la (26/11).
                totais = estado.setdefault("totais", {})
                if total:
                    totais[nome_fatia] = total
                else:
                    totais.setdefault(nome_fatia, 0)
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
                # Sobreposição de 1 item entre páginas (2026-11-15): itens entram
                # e saem do Mercado durante a varredura e a lista "escorrega"; na
                # 1a volta vieram 642 repetidos e um tanto parecido foi pulado
                # (~3,5%, a AWP | Dragon Lore entre eles). Repetido é inofensivo
                # (grava por cima); pulado só voltava numa próxima volta.
                ultima = int(estado["start"]) + len(pagina) >= total
                avanco = (len(pagina) if ultima or len(pagina) <= _SOBREPOSICAO
                          else len(pagina) - _SOBREPOSICAO)
                estado["start"] = int(estado["start"]) + avanco
                if not pagina or estado["start"] >= total:
                    if _proxima_fatia(estado):
                        motivo = _finalizar_rodada(estado)
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
              "totais", "motivo", "ultima_pagina_ts", "erro_404_seguidos",
              "erro_404_start", "erros_404_fatias",
               "erros_404_fatias_rodada", "fim_ultima_rodada_ts",
                "inicio_ts", "retomar", "fatias_puladas")
    saida = {k: estado.get(k) for k in chaves if k in estado}
    # Estado de 25/11 não tem estes campos: mostra desde já o ponto que a
    # próxima rodada vai usar, sem precisar esperar ela começar (26/11).
    if not isinstance(estado.get("retomar"), dict):
        legado = _retomar_legado(estado)
        if legado is not None:
            saida["retomar"] = legado
    saida.setdefault("retomar", None)
    saida.setdefault("fatias_puladas", [])
    # Cotação usada para converter os preços (dólar → reais), com quantos
    # itens a mediram -- pra acompanhar se ela sair do normal (2026-11-15).
    taxa = cambio() if saida else None  # sem catálogo, sem cotação
    if taxa:
        saida["cotacao_brl_por_usd"] = round(taxa, 4)
        try:
            salvo = json.loads(_caminho_cambio().read_text(encoding="utf-8"))
            saida["cotacao_pares"] = salvo.get("pares")
            saida["cotacao_ts"] = salvo.get("ts")
        except Exception:
            pass
    return saida


# ── Leitura (o site) ─────────────────────────────────────────────────
# Só SQLite local: nenhuma consulta à Steam. Sem banco (dev, testes, ou
# antes da 1a varredura), tudo volta vazio e o site segue como antes.

def _conectar_leitura() -> "sqlite3.Connection | None":
    caminho = _caminho_banco()
    if not caminho.exists():
        return None
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA query_only=ON")
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
        taxa = cambio()
        partes.append("preco <= ?")
        # O banco está em dólar; o filtro chega em reais.
        args.append(float(filtros["preco_max"]) / taxa if taxa else -1.0)
    partes.append("preco IS NOT NULL")
    if excluir:
        partes.append(f"nome NOT IN ({','.join('?' * len(excluir))})")
        args.extend(excluir)
    return " AND ".join(partes), args


def consultar(filtros: dict, excluir: "list[str]" = (), ordenar: str = "a_venda",
              limite: int = 12, offset: int = 0,
              contar: bool = True) -> "tuple[int, list[dict]]":
    """(total, itens) do catálogo que batem com os filtros, sem os
    `excluir` (os itens com nota, que a lista já mostra antes). Com
    `contar=False` não conta (o total volta 0): a home já tem o total
    de `contar_por_categoria`."""
    conn = _conectar_leitura()
    if conn is None:
        return 0, []
    try:
        where, args = _where(filtros, list(excluir))
        total = conn.execute(f"SELECT COUNT(*) FROM itens WHERE {where}",
                             args).fetchone()[0] if contar else 0
        ordem = "preco ASC" if ordenar == "preco" else "a_venda DESC, nome"
        linhas = conn.execute(
            f"SELECT * FROM itens WHERE {where} ORDER BY {ordem} "
            "LIMIT ? OFFSET ?", [*args, max(0, int(limite)), max(0, int(offset))]
        ).fetchall() if limite > 0 else []
        taxa = cambio()
        return total, [_em_reais(dict(r), taxa) for r in linhas]
    except sqlite3.Error:
        _logger.warning("leitura do catálogo falhou", exc_info=True)
        return 0, []
    finally:
        conn.close()


def parecidos(nome: str, limite: int = 6) -> "list[dict]":
    """Itens de nome parecido, para a página de item não encontrado
    (revisão 17/11: nome digitado errado ou link antigo caía num "essa
    página não existe" sem saída). Usa as palavras do nome, sem o
    desgaste entre parênteses, e tira uma do fim por vez até achar algo:
    "AK-47 | Redlin" acha os AK-47 | Redline."""
    base = re.sub(r"\([^)]*\)", " ", nome or "")
    palavras = [p for p in re.split(r"[\s|★™]+", texto_busca(base))
                if len(p) >= 2 and p != "or" and any(ch.isalnum() for ch in p)][:6]
    while palavras:
        _total, linhas = consultar({"busca": " ".join(palavras)}, [],
                                   limite=limite, contar=False)
        if linhas:
            return linhas
        palavras = palavras[:-1]
    return []


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
        return _em_reais(dict(r), cambio()) if r else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def metadados(nomes: "list[str]") -> "dict[str, dict]":
    """{nome: {"icon", "raridade"}} do catálogo, para completar item da
    coleta que chegou sem imagem (worker). Só leitura local, sem rede."""
    nomes = [n for n in nomes if n]
    conn = _conectar_leitura()
    if conn is None or not nomes:
        if conn is not None:
            conn.close()
        return {}
    try:
        saida: dict = {}
        for i in range(0, len(nomes), 500):
            lote = nomes[i:i + 500]
            marcas = ",".join("?" * len(lote))
            for r in conn.execute(
                    f"SELECT nome, icon, raridade, atualizado_em FROM itens WHERE nome IN ({marcas})",
                    lote):
                saida[r["nome"]] = {"icon": r["icon"], "raridade": r["raridade"],
                                    "atualizado_em": r["atualizado_em"]}
        return saida
    except sqlite3.Error:
        return {}
    finally:
        conn.close()


# ── Moeda (achado 2026-11-15) ─────────────────────────────────────────
# A busca do Mercado (/market/search/render) IGNORA o currency=7: sem
# login, `sell_price` vem sempre em centavos de DÓLAR ("$5.19"). O banco
# guarda o valor como veio (dólar) e toda leitura converte para reais com
# a cotação que a própria Steam usa, medida sem consulta nova: a mediana
# de preço em reais (coleta com nota, priceoverview com currency=7) ÷
# preço em dólar (catálogo) dos itens que estão nos dois. Sem cotação
# confiável, o catálogo não mostra preço (melhor que um número errado).
_CAMBIO_TTL_S = 600
_CAMBIO_MIN_PARES = 10
_CAMBIO_FAIXA = (2.0, 15.0)
_cambio_cache: dict = {"ts": 0.0, "valor": None}
# Testes fixam a cotação (conftest); em produção fica None.
CAMBIO_FIXO: "float | None" = None


def _caminho_cambio() -> Path:
    return _paths.DATA_DIR / "catalogo_cambio.json"


def _precos_usd(nomes: "list[str]") -> "dict[str, float]":
    """Preço como a Steam mandou (dólar), sem converter."""
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


def medir_cambio(precos_brl: "dict[str, float]") -> "tuple[float | None, int]":
    """(cotação BRL por USD, pares usados) a partir de {nome: preço em
    reais}. Só itens de pelo menos US$ 1 (abaixo disso o arredondamento
    em centavos distorce a razão)."""
    usd = _precos_usd(list(precos_brl))
    razoes = sorted(precos_brl[n] / v for n, v in usd.items()
                    if v and v >= 1.0 and precos_brl.get(n))
    if len(razoes) < _CAMBIO_MIN_PARES:
        return None, len(razoes)
    meio = len(razoes) // 2
    mediana = razoes[meio] if len(razoes) % 2 else (razoes[meio - 1] + razoes[meio]) / 2
    if not _CAMBIO_FAIXA[0] <= mediana <= _CAMBIO_FAIXA[1]:
        return None, len(razoes)
    return mediana, len(razoes)


def cambio() -> "float | None":
    """Reais por dólar para os preços do catálogo (cache de 10 min; a
    última medida boa fica salva como reserva)."""
    if CAMBIO_FIXO is not None:
        return CAMBIO_FIXO
    agora = time.time()
    if agora - _cambio_cache["ts"] < _CAMBIO_TTL_S:
        return _cambio_cache["valor"]
    valor = None
    try:
        from lodout import scan_store
        scan = scan_store.load_last_scan() or {}
        brl = {r["name"]: float(r["price"]) for r in scan.get("results") or []
               if r.get("name") and isinstance(r.get("price"), (int, float)) and r["price"] > 0}
        valor, pares = medir_cambio(brl)
        if valor is not None:
            _paths.atomic_write_text(_caminho_cambio(), json.dumps(
                {"cambio": valor, "pares": pares, "ts": agora}))
    except Exception:
        _logger.warning("cotação do catálogo: medida falhou", exc_info=True)
    if valor is None:
        try:
            salvo = json.loads(_caminho_cambio().read_text(encoding="utf-8"))
            v = float(salvo.get("cambio"))
            valor = v if _CAMBIO_FAIXA[0] <= v <= _CAMBIO_FAIXA[1] else None
        except Exception:
            valor = None
    _cambio_cache.update(ts=agora, valor=valor)
    return valor


def _em_reais(linha: dict, taxa: "float | None") -> dict:
    """Linha do banco com o preço convertido para reais (None sem cotação)."""
    if linha.get("preco") is not None:
        linha["preco"] = round(linha["preco"] * taxa, 2) if taxa else None
    return linha


def precos(nomes: "list[str]") -> "dict[str, float]":
    """{nome: preço do dia em reais} para os nomes que o catálogo tem."""
    taxa = cambio()
    if not taxa:
        return {}
    return {n: round(v * taxa, 2) for n, v in _precos_usd(nomes).items()}


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
