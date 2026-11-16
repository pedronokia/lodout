"""Blueprint de conta: "Entrar com Steam" + portfólio pessoal.

O dashboard público (`server.py`/`index.html`) continua anônimo e sem
conta, como na Fase 1 -- isto aqui é opcional, só pra quem quiser
acompanhar a própria carteira.
"""
from __future__ import annotations

import json
import math
import secrets
import time
import urllib.parse
from pathlib import Path

from flask import (
    Blueprint, flash, jsonify, make_response, redirect, render_template, request,
    send_file, session, url_for,
)

from lodout import _paths, portfolio, scan_store
from lodout.localization import localize_name
from lodout.prices import PriceCache
from lodout.public_site import (
    catalogo, fmt, inventario, raridade, steam_openid, user_history, user_portfolio,
    user_store, user_trades, user_vendidos, user_watchlist,
)
from lodout.public_site.auth import csrf_protect, csrf_token, login_required
from lodout.public_site.rate_limit import (
    CUSTO_MAX_HITS, CUSTO_WINDOW_S, LOGIN_MAX_HITS, LOGIN_WINDOW_S,
    MUTATION_MAX_HITS, MUTATION_WINDOW_S, rate_limited,
)
from lodout.public_site.profile_fetcher import (
    apagar_perfil_cache, caminho_avatar, fetch_public_profile,
)

bp = Blueprint("account", __name__)


def _openid_return_to_matches(expected: "str | None") -> bool:
    if not expected or request.args.get("openid.return_to") != expected:
        return False

    expected_url = urllib.parse.urlsplit(expected)
    current_url = urllib.parse.urlsplit(request.base_url)
    if (expected_url.scheme, expected_url.netloc, expected_url.path) != (
            current_url.scheme, current_url.netloc, current_url.path):
        return False

    expected_query = urllib.parse.parse_qs(
        expected_url.query, keep_blank_values=True)
    return all(
        request.args.getlist(key) == values
        for key, values in expected_query.items()
    )


def _idade_dos_precos(quandos: "list[float]") -> "str | None":
    """De quando são os preços da lista, visível também no celular (a dica
    por item só aparece passando o mouse -- revisão 2026-11-16). Vale o
    mais antigo: "Preços coletados há até 20 h".
    """
    if not quandos:
        return None
    novo = scan_store.idade_txt(max(quandos))
    velho = scan_store.idade_txt(min(quandos))
    if novo == velho:
        return f"Preços coletados {velho}."
    return f"Preços coletados {velho.replace('há ', 'há até ', 1)}."


def _preco_do_dia(positions: "list[dict]"):
    """Preço de cada item da conta: o da coleta com nota quando existe;
    senão o do catálogo amplo (todo o Mercado, 1x por dia). Só leitura
    local, sem rede (catalogo-grande.md, fase 2)."""
    cache = PriceCache()
    nomes = [p.get("name") for p in positions]
    do_catalogo = catalogo.precos(nomes)
    datas: dict = {}

    def _preco(nome: str):
        preco = cache.get(nome)
        if preco is not None:
            datas[nome] = cache.ts(nome)
            return preco
        return do_catalogo.get(nome)

    meta_cat: dict = {}

    def _data(nome: str):
        """Quando o preço usado foi coletado (para "coletado há 3 h").
        As datas do catálogo vêm numa leitura só, na primeira pergunta."""
        if nome in datas:
            return datas[nome]
        if nome in do_catalogo:
            if not meta_cat:
                meta_cat.update(catalogo.metadados(list(do_catalogo)) or {"": {}})
            return (meta_cat.get(nome) or {}).get("atualizado_em")
        return None
    _preco.data = _data
    return _preco


def _scan_lookup() -> dict:
    """{name: resultado bruto} do último scan público -- só pro ícone/
    raridade/nota (achado 2026-11-07: o portfólio não mostrava ícone
    nenhum, igual watchlist/trades antes do mesmo fix -- ver
    raridade.py)."""
    scan = scan_store.load_last_scan()
    if not scan:
        return {}
    return {r["name"]: r for r in scan["results"]}


# Meta de lucro da pessoa (2026-11-15): começa em 20%, ela escolhe. Fica
# em user_data (kind "preferencias"), junto do resto do que é dela.
_META_LUCRO_PADRAO = 20
_META_LUCRO_OPCOES = (10, 20, 30, 50, 100)
_META_LUCRO_MAX = 500


def _meta_lucro(steamid: str) -> int:
    prefs = user_store.load_user_json(steamid, "preferencias", {})
    try:
        meta = int((prefs or {}).get("meta_lucro_pct", _META_LUCRO_PADRAO))
    except (TypeError, ValueError):
        return _META_LUCRO_PADRAO
    return meta if 1 <= meta <= _META_LUCRO_MAX else _META_LUCRO_PADRAO


def _formatar_linhas(avaliacao: dict, meta_pct: int = _META_LUCRO_PADRAO) -> dict:
    """Acrescenta campos *_fmt pro template -- mesmo padrão de
    `server.py:_candidatos` (formata em Python, template fica simples).

    Por item com custo conhecido: o preço de venda para empatar (custo +
    a taxa da Steam) e o preço para lucrar `meta_pct` % já com a taxa --
    a pergunta de quem comprou para revender (2026-11-15)."""
    por_nome_scan = _scan_lookup()
    # Sem imagem na coleta nem no inventário (ex.: item adicionado à mão):
    # a imagem vem do catálogo do Mercado, leitura local (2026-11-15).
    sem_imagem = [r["name"] for r in avaliacao["rows"]
                  if not (por_nome_scan.get(r["name"]) or {}).get("icon") and not r.get("icon")]
    do_catalogo = raridade.completar_com_catalogo({}, sem_imagem) if sem_imagem else {}
    for row in avaliacao["rows"]:
        custo = row.get("cost") or 0
        if row.get("has_cost") and custo > 0:
            empate = portfolio.break_even_price(custo)
            row["empate"] = empate
            row["empate_fmt"] = fmt.brl(empate)
            row["alvo_fmt"] = fmt.brl(empate * (1 + meta_pct / 100))
        raw = por_nome_scan.get(row["name"])
        row["name_fmt"] = localize_name(row["name"])
        # Nome em cima, desgaste embaixo em cinza (polimento, 2026-11-15).
        row["nome_curto"], row["exterior_fmt"] = row["name_fmt"], None
        ext = catalogo.exterior_do_item(row["name"])
        if ext:
            rotulo = catalogo.EXTERIORES[ext][1]
            sufixo = f" ({rotulo})"
            if row["name_fmt"].endswith(sufixo):
                row["nome_curto"] = row["name_fmt"][:-len(sufixo)]
                row["exterior_fmt"] = rotulo
        row["busca_extra"] = _palavras_busca(row["name"])
        row["price_fmt"] = fmt.brl(row.get("price"))
        if row.get("price") is not None:
            row["valor_total_fmt"] = fmt.brl(row["price"] * (row.get("quantity") or 1))
        row["cost_fmt"] = fmt.brl(row.get("cost"))
        row["pnl_fmt"] = fmt.brl(row.get("pnl"))
        row["confira"] = _confira(custo if row.get("has_cost") else None, row.get("price"))
        row["pnl_pct_fmt"] = _pct_curto(row.get("pnl_pct")) \
            if row.get("has_cost") and row.get("pnl") is not None and custo > 0 else None
        row["score"] = raw.get("score") if raw else None
        # Item do inventário fora da coleta: a imagem vem do próprio
        # inventário (hash do CDN da Steam), em vez de ficar sem foto.
        row.update(raridade.icone_raridade(
            raw or do_catalogo.get(row["name"]) or {"icon": row.get("icon")}))
    t = avaliacao["totals"]
    # Quanto valem hoje os itens sem valor pago: o lucro em destaque não
    # os inclui, e o cartão "Sem valor pago" diz isso (crítica de 15/11).
    t["market_sem_custo"] = sum(
        (r.get("price") or 0) * (r.get("quantity") or 1)
        for r in avaliacao["rows"] if not r.get("has_cost"))
    t["cost_fmt"] = fmt.brl(t.get("cost"))
    t["cost_known_fmt"] = fmt.brl(t.get("cost_known"))
    t["market_fmt"] = fmt.brl(t.get("market"))
    t["net_if_sold_fmt"] = fmt.brl(t.get("net_if_sold"))
    t["pnl_fmt"] = fmt.brl(t.get("pnl"))
    avaliacao["textos"] = _textos_totais(t)
    return avaliacao


# Palavras em português para a busca da conta achar o tipo do item cujo
# nome a Steam só tem em inglês: "cápsula" não achava "Sticker Capsule",
# nem "luva" achava "Sport Gloves" (revisão 2026-11-16).
_PALAVRAS_TIPO = (
    ("Autograph Capsule", "cápsula de autógrafo"),
    ("Capsule", "cápsula"),
    (" Case", "caixa"),
    ("Gloves", "luva luvas"),
    ("Hand Wraps", "luva luvas faixas"),
    ("Souvenir", "lembrança"),
)
# Cápsulas antigas sem "Capsule" no nome ("EMS Katowice 2014 Legends",
# "2020 RMR Challengers").
_CAPSULA_SEM_NOME = ("Legends", "Challengers", "Contenders")


def _palavras_busca(nome: str) -> str:
    if nome.startswith("Sticker |"):
        return ""  # o nome já aparece como "Adesivo | …"
    extra = [pt for en, pt in _PALAVRAS_TIPO if en in nome]
    if nome.startswith("★") and "Gloves" not in nome and "Hand Wraps" not in nome:
        extra.append("faca")
    if not extra and "|" not in nome and any(p in nome for p in _CAPSULA_SEM_NOME):
        extra.append("cápsula")
    return " ".join(extra)


def _confira(custo: "float | None", preco: "float | None") -> str:
    """Aviso discreto quando o valor pago parece digitado errado: muito
    abaixo (menos de 1/5) ou muito acima (mais de 10x) do preço de hoje.
    Não diz que está errado -- só pede pra conferir (2026-11-15, depois
    do problema que cortava números na digitação)."""
    if not custo or not preco:
        return ""
    if custo < preco / 5:
        return "confira: bem abaixo do preço"
    if custo > preco * 10:
        return "confira: bem acima do preço"
    return ""


def _pct_curto(pct: "float | None") -> "str | None":
    """"−88%", "+12%", "0%": porcentagem inteira com o sinal de menos
    tipográfico, para a linha do item (o cartão usa uma casa decimal)."""
    if pct is None:
        return None
    n = round(pct)
    return ("+" if n > 0 else "\u2212" if n < 0 else "") + f"{abs(n)}%"


def _textos_totais(t: dict) -> dict:
    """Textos dos cartões do topo e do aviso de itens sem valor pago.
    A página e a resposta JSON de "salvar valor pago" usam os mesmos,
    pra o topo atualizar sem recarregar e sem divergir do servidor."""
    # Itens, não linhas: lotes do mesmo item contam uma vez (revisão 16/11
    # -- separar em lotes fazia "500 itens" virar "501 itens").
    n = t.get("itens", t.get("positions")) or 0
    com = t.get("itens_com_custo", t.get("known_cost")) or 0
    sem = t.get("itens_sem_custo", t.get("unknown_cost")) or 0
    pnl, pct = t.get("pnl"), t.get("pnl_pct")
    if pnl is None:
        lucro_sub = "informe o valor pago para ver"
    else:
        sinal = "+" if pct and pct > 0.05 else ("\u2212" if pct and pct < -0.05 else "")
        base = (f"{sinal}{fmt.pct(abs(pct))}% do que você pagou" if pct is not None
                else "dos itens com o valor pago")
        # Com itens sem valor pago, o lucro é só de parte da carteira: diz
        # de quantos (crítica de 15/11, problema P1). Conta os que entraram
        # na conta de verdade: item com valor pago mas sem preço hoje fica
        # de fora (revisão 16/11 -- dizia "10 itens" com a conta feita em 9).
        no_lucro = t.get("itens_no_lucro", t.get("pnl_positions", com))
        sem_preco = max(0, com - no_lucro)
        if (sem or sem_preco) and pct is not None:
            quantos = "de 1 item" if no_lucro == 1 else f"dos {no_lucro} itens"
            lucro_sub = (f"{sinal}{fmt.pct(abs(pct))}% · só {quantos} com valor pago"
                         + (" e preço hoje" if sem_preco else ""))
        else:
            lucro_sub = base
    if sem:
        aviso = (f"{sem} {'item está' if sem == 1 else 'itens estão'} sem o "
                 "valor pago. Preencha para ver por quanto vender e para "
                 f"{'ele entrar' if sem == 1 else 'eles entrarem'} no lucro.")
    else:
        aviso = ""
    falta_valor = float(t.get("market_sem_custo") or 0)
    return {
        "valor": t.get("market_fmt") or fmt.brl(t.get("market")),
        "valor_sub": f"{n} {'item' if n == 1 else 'itens'}",
        "liquido": t.get("net_if_sold_fmt") or fmt.brl(t.get("net_if_sold")),
        "liquido_sub": "você recebe " + (t.get('net_if_sold_fmt') or fmt.brl(t.get('net_if_sold'))).replace(" ", "\u00a0") + " depois da taxa",
        "falta_texto": f"{sem} {'item' if sem == 1 else 'itens'}" if sem else "",
        "falta_sub": (f"valem {fmt.brl(falta_valor)} hoje" if sem and falta_valor else ""),
        "pago": t.get("cost_known_fmt") or fmt.brl(t.get("cost_known")),
        "pago_sub": f"em {com} de {n} {'item' if n == 1 else 'itens'}",
        "lucro": fmt.brl(pnl) if pnl is not None else "—",
        "lucro_sub": lucro_sub,
        "lucro_classe": ("valor-positivo" if pnl and pnl > 0 else
                         "valor-negativo" if pnl and pnl < 0 else
                         "card-valor-texto" if pnl is None else ""),
        "aviso_sem_custo": aviso,
        "com_valor": com,
        "total_itens": n,
    }


@bp.route("/login")
@rate_limited(LOGIN_MAX_HITS, LOGIN_WINDOW_S)
def login():
    state = secrets.token_urlsafe(32)
    return_to = url_for(
        "account.login_callback", state=state, _external=True)
    session["steam_openid_return_to"] = return_to
    realm = request.url_root
    return redirect(steam_openid.login_redirect_url(return_to, realm))


@bp.route("/login/callback")
@rate_limited(LOGIN_MAX_HITS, LOGIN_WINDOW_S)
def login_callback():
    return_to = session.get("steam_openid_return_to")
    if not _openid_return_to_matches(return_to):
        return redirect(url_for("index"))
    session.pop("steam_openid_return_to", None)

    steamid = steam_openid.verify_callback(request.args.to_dict())
    if not steamid:
        return redirect(url_for("index"))
    perfil = fetch_public_profile(steamid) or {}
    user_store.upsert_user(
        steamid,
        persona_name=perfil.get("name"),
        avatar_url=perfil.get("avatar_url"),
    )
    session["steamid"] = steamid
    session.permanent = True  # 30 dias ou até "Sair" (PERMANENT_SESSION_LIFETIME)
    # Inventário sincroniza sozinho a cada login (ação da própria pessoa),
    # em segundo plano pra não deixar o login lento (conta-inventario.md).
    inventario.sincronizar_em_segundo_plano(steamid)
    return redirect(url_for("account.conta"))


@bp.route("/conta/avatar.jpg")
@login_required
def avatar():
    path = caminho_avatar(session["steamid"])
    if path is None:
        return "", 404
    resp = send_file(path, mimetype="image/jpeg")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@bp.route("/logout")
def logout():
    # Sair limpa o que é da conta: mensagens pendentes ("entrou na sua
    # lista"…) não podem aparecer para a próxima pessoa que entrar no mesmo
    # navegador, e o token de formulário recomeça (revisão 2026-11-16).
    # O login de admin é separado e continua.
    session.pop("steamid", None)
    session.pop("csrf_token", None)
    session.pop("_flashes", None)
    return redirect(url_for("index"))


@bp.route("/conta")
@login_required
def conta():
    steamid = session["steamid"]
    positions = user_portfolio.load_positions(steamid)
    # Preço vem do mesmo cache compartilhado da Fase 1 -- leitura pura,
    # sem rede. Se o item nunca foi escaneado, a linha some sem preço
    # quando a Steam não respondeu).
    preco_do_dia = _preco_do_dia(positions)
    avaliacao_bruta = portfolio.evaluate_portfolio(positions, preco_do_dia)
    quandos = []
    for row in avaliacao_bruta["rows"]:
        quando = preco_do_dia.data(row["name"]) if row.get("price") is not None else None
        row["preco_idade"] = scan_store.idade_txt(quando) if quando else None
        if quando:
            quandos.append(quando)
    # Grava o ponto de histórico ANTES de formatar -- precisa do valor
    # numérico (totals.market), não do "_fmt" em string. Dedup embutido:
    # visitar /conta duas vezes seguidas sem nada mudar não dobra a série.
    itens_agora: dict = {}
    for pos in positions:
        itens_agora[pos["name"]] = itens_agora.get(pos["name"], 0) + int(pos.get("quantity") or 1)
    serie = user_history.record_if_changed(
        steamid, avaliacao_bruta["totals"]["market"], itens=itens_agora)
    mudanca = _mudanca_recente(serie)
    _marcar_lotes(avaliacao_bruta["rows"], positions)
    # Mais valioso primeiro (2026-11-15): com o inventário inteiro na
    # lista, a ordem de chegada deixava a faca no meio dos adesivos.
    # Lotes do mesmo item ficam juntos (ordem pelo valor do item todo).
    valor_por_nome: dict = {}
    for r in avaliacao_bruta["rows"]:
        valor_por_nome[r["name"]] = valor_por_nome.get(r["name"], 0) + \
            (r.get("price") or 0) * (r.get("quantity") or 1)
    avaliacao_bruta["rows"].sort(
        key=lambda r: (-valor_por_nome[r["name"]], r["name"]))
    meta = _meta_lucro(steamid)
    estado_inv = inventario.estado(steamid)
    # Busca interrompida (servidor reiniciou no meio): o "buscando…" não
    # fica preso -- depois de 5 min vale o último estado conhecido.
    if estado_inv.get("em_andamento") and \
            time.time() - float(estado_inv.get("iniciado_ts") or 0) > 300:
        estado_inv["em_andamento"] = False
    avaliacao = _formatar_linhas(avaliacao_bruta, meta)
    avaliacao["fora_n"] = len({r["name"] for r in avaliacao["rows"] if r.get("fora_desde")})
    # `usuario` NÃO é passado aqui de propósito (2026-10-27): o context
    # processor `_inject_usuario` (server.py) já busca o mesmo
    # `user_store.get_user(steamid)` pra TODO template com sessão ativa
    # -- passar de novo aqui só dobrava a leitura SQLite (mesma conexão
    # aberta/fechada duas vezes) sem mudar nenhum valor, já que é
    # exatamente o mesmo steamid da sessão.
    return render_template(
        "conta.html", avaliacao=avaliacao,
        csrf_token=csrf_token(),
        meta_lucro=meta,
        inventario_estado=estado_inv,
        inventario_idade=(scan_store.idade_txt(estado_inv["ts"])
                          if estado_inv.get("ts") else None),
        meta_lucro_opcoes=_META_LUCRO_OPCOES,
        mudanca_valor=mudanca,
        mostrar_recuperar=time.time() < RECUPERAR_ATE_TS,
        idade_precos=_idade_dos_precos(quandos),
        taxa_steam_pct=round(portfolio.STEAM_FEE * 100),
    )


# Base da comparação do cartão "Vale hoje": o ponto mais recente com pelo
# menos 20 h. Antes era o ponto anterior do histórico (só grava quando o
# total muda), então reabrir a conta minutos depois repetia o mesmo
# "+R$ X desde a última vez" (revisão 2026-11-16).
_MUDANCA_IDADE_MIN_S = 20 * 3600


def _mudanca_recente(serie: "list[dict]", agora: "float | None" = None) -> "dict | None":
    """Quanto o total de "Vale hoje" mudou desde ontem (ou nos últimos N
    dias, se o ponto de ~24 h atrás não existir). Inclui itens que
    entraram ou saíram, não só preço -- o título explica."""
    if not serie or len(serie) < 2:
        return None
    agora = time.time() if agora is None else agora
    atual = serie[-1]
    antes = None
    for ponto in reversed(serie[:-1]):
        if agora - float(ponto.get("ts") or 0) >= _MUDANCA_IDADE_MIN_S:
            antes = ponto
            break
    if antes is None:
        return None
    # Ponto zerado = visita com a conta ainda vazia (antes do inventário
    # chegar): comparar com ele dava "+ o valor inteiro" (achado
    # 2026-11-15, print do usuário). Sem base, sem frase.
    if float(antes.get("total") or 0) <= 0 or float(atual.get("total") or 0) <= 0:
        return None
    # Dobrou ou caiu à metade de uma vez: quase sempre é a carteira que
    # mudou de tamanho (inventário novo) ou uma correção de preço do site
    # (2026-11-15: catálogo em dólar), não o mercado. Melhor não dizer.
    razao = float(atual["total"]) / float(antes["total"])
    if razao > 2 or razao < 0.5:
        return None
    diff = float(atual.get("total") or 0) - float(antes.get("total") or 0)
    if abs(diff) < 0.005:
        return None
    idade = agora - float(antes.get("ts") or 0)
    dias = int(idade // 86400)
    periodo = "desde ontem" if idade < 48 * 3600 else f"nos últimos {dias} dias"
    # Itens entraram ou saíram desde a base: a diferença não é só preço,
    # e a frase diz isso (revisão 16/11; antes só o title, que celular e
    # teclado não mostram). Pontos antigos, sem `comp`, ficam sem nota.
    nota = ""
    if antes.get("comp") and atual.get("comp") and antes["comp"] != atual["comp"]:
        ua, ub = int(atual.get("unid") or 0), int(antes.get("unid") or 0)
        nota = ("contando itens que entraram" if ua > ub else
                "contando itens que saíram" if ua < ub else
                "contando itens que entraram e saíram")
    return {
        "nota": nota,
        "texto": ("+" if diff > 0 else "") + fmt.brl(diff),
        "classe": "valor-positivo" if diff > 0 else "valor-negativo",
        "periodo": periodo,
        "quando": scan_store.idade_txt(antes.get("ts") or 0, now=agora),
    }


def resumo_na_conta(steamid: "str | None", name: str) -> "dict | None":
    """O que a pessoa tem deste item, pra página do item ("Na sua conta",
    2026-11-15): unidades, e por lote com valor pago, por quanto vender."""
    if not steamid:
        return None
    lotes = [p for p in user_portfolio.load_positions(steamid) if p.get("name") == name]
    # Vendas deste item, marcadas com "Vendi" (revisão 30, 16/11): a
    # página do item mostra também o que a pessoa já vendeu dele.
    vendas = []
    for v in user_vendidos.load(steamid):
        if v.get("name") != name:
            continue
        pnl_v = float(v.get("pnl") or 0)
        vendas.append({
            "quantidade": int(v.get("quantity") or 1),
            "preco_fmt": fmt.brl(v.get("sell_price")),
            "data": fmt.dia_mes_br(float(v.get("sell_ts") or 0)),
            "valor_fmt": fmt.brl(abs(pnl_v)),
            "tipo": "lucro" if pnl_v > 0.005 else ("prejuízo" if pnl_v < -0.005 else "empate"),
            "classe": "valor-positivo" if pnl_v > 0.005 else ("valor-negativo" if pnl_v < -0.005 else ""),
            "ts": float(v.get("sell_ts") or 0),
        })
    vendas.sort(key=lambda v: -v["ts"])
    if not lotes and not vendas:
        return None
    # Fora do inventário (anunciado no Mercado ou vendido, revisão 30).
    fora = [p for p in lotes if p.get("fora_desde")]
    fora_unid = sum(int(p.get("quantity") or 1) for p in fora)
    anunciado_unid = sum(int(p.get("quantity") or 1) for p in fora if p.get("anunciado"))
    fora_quando = fmt.dia_mes_br(min(float(p["fora_desde"]) for p in fora)) if fora else None
    meta = _meta_lucro(steamid)
    unidades = sum(int(p.get("quantity") or 1) for p in lotes)
    com_valor = []
    for p in lotes:
        custo = p.get("cost")
        if portfolio.has_cost_basis(p) and custo:
            empate = portfolio.break_even_price(float(custo))
            com_valor.append({
                "quantidade": int(p.get("quantity") or 1),
                "pago_fmt": fmt.brl(float(custo)),
                "empate_fmt": fmt.brl(empate),
                "alvo_fmt": fmt.brl(empate * (1 + meta / 100)),
            })
    sem_valor = unidades - sum(l["quantidade"] for l in com_valor)
    # Lucro se vender hoje (revisão 2026-11-16): o mesmo preço e a mesma
    # conta da página "Minha conta", só dos lotes com valor pago.
    lucro = None
    try:
        preco = _preco_do_dia(lotes)(name)
    except Exception:
        preco = None
    if preco is not None and com_valor:
        pnl = custo_total = 0.0
        for p in lotes:
            if portfolio.has_cost_basis(p) and p.get("cost"):
                d = portfolio.position_pnl(float(p["cost"]), float(preco), int(p.get("quantity") or 1))
                pnl += d["pnl"]
                custo_total += d["cost_total"]
        pct = pnl / custo_total * 100 if custo_total else None
        lucro = {
            "valor_fmt": fmt.brl(abs(pnl)),
            "tipo": "lucro" if pnl > 0.005 else ("prejuízo" if pnl < -0.005 else "empate"),
            "classe": "valor-positivo" if pnl > 0.005 else ("valor-negativo" if pnl < -0.005 else ""),
            "pct_fmt": _pct_curto(pct) if pct is not None else "",
        }
    return {"unidades": unidades, "lotes": com_valor, "sem_valor": sem_valor, "meta": meta,
            "lucro": lucro, "busca": localize_name(name),
            "fora_unid": fora_unid, "anunciado_unid": anunciado_unid,
            "fora_quando": fora_quando, "vendas": vendas}


def _marcar_lotes(rows: "list[dict]", positions: "list[dict]") -> None:
    """Leva o id do lote de cada posição para a linha (mesma ordem: uma
    linha por posição) e numera os lotes do mesmo item ("lote 1 de 2")."""
    total: dict = {}
    for pos in positions:
        total[pos.get("name")] = total.get(pos.get("name"), 0) + 1
    dentro: dict = {}
    for pos in positions:
        if not pos.get("fora_desde"):
            dentro[pos.get("name")] = dentro.get(pos.get("name"), 0) + 1
    visto: dict = {}
    juntar_mostrado: set = set()
    for row, pos in zip(rows, positions):
        row["lote"] = pos.get("lote")
        n = total.get(pos.get("name"), 1)
        visto[pos.get("name")] = visto.get(pos.get("name"), 0) + 1
        row["lotes_total"] = n
        row["lote_numero"] = visto[pos.get("name")]
        # Fora do inventário (anunciado no Mercado ou vendido, revisão
        # 16/11): a pessoa diz se vendeu. Sem "separar"/"juntar" nela.
        fora = pos.get("fora_desde")
        row["fora_desde"] = fora
        row["fora_quando"] = fmt.dia_mes_br(float(fora)) if fora else None
        row["anunciado"] = bool(fora and pos.get("anunciado"))
        row["origem"] = pos.get("source")
        # "juntar lotes" na 1ª linha no inventário, com 2+ lotes no inventário.
        row["mostra_juntar"] = bool(
            not fora and dentro.get(pos.get("name"), 0) > 1
            and pos.get("name") not in juntar_mostrado)
        if row["mostra_juntar"]:
            juntar_mostrado.add(pos.get("name"))


@bp.route("/conta/posicoes/<name>/separar", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def separar_lote(name: str):
    """Pagou valores diferentes pelo mesmo item: separa unidades num lote
    novo, sem valor pago, pra pessoa informar (pedido 2026-11-15)."""
    steamid = session["steamid"]
    try:
        quantidade = int((request.form.get("quantidade") or "").strip())
    except ValueError:
        quantidade = 0
    lote = (request.form.get("lote") or "").strip() or None
    if user_portfolio.separar(steamid, name, quantidade, lote=lote):
        flash(f"Separado: {quantidade} {'unidade ficou' if quantidade == 1 else 'unidades ficaram'} "
              "numa linha própria, sem valor pago. Informe quanto você pagou nela.", "success")
    else:
        flash("Não deu para separar: escolha de 1 até uma unidade a menos que o total da linha.", "error")
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/juntar", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def juntar_lotes(name: str):
    """Junta os lotes de um item de novo, com o valor médio ponderado."""
    steamid = session["steamid"]
    resultado = user_portfolio.juntar(steamid, name)
    if resultado == "ok":
        flash("Lotes juntados numa linha só, com o valor médio que você pagou.", "success")
    elif resultado == "misto":
        flash("Para juntar, informe o valor pago de todos os lotes desse item "
              "(ou de nenhum): sem o valor de um lote, o Lodout teria que inventar um preço.", "error")
    return redirect(url_for("account.conta"))


@bp.route("/conta/meta", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def definir_meta():
    """Meta de lucro (%) usada no preço de venda de cada item."""
    steamid = session["steamid"]
    try:
        meta = int((request.form.get("meta") or "").strip())
    except ValueError:
        meta = 0
    quer_json = "application/json" in (request.headers.get("Accept") or "")
    if not 1 <= meta <= _META_LUCRO_MAX:
        if quer_json:
            return jsonify({"ok": False}), 400
        flash(f"A meta de lucro precisa ser um número entre 1 e {_META_LUCRO_MAX}.",
              "error")
        return redirect(url_for("account.conta"))
    prefs = user_store.load_user_json(steamid, "preferencias", {}) or {}
    prefs["meta_lucro_pct"] = meta
    user_store.save_user_json(steamid, "preferencias", prefs)
    if quer_json:
        # conta.js recalcula os preços na própria página (sem recarregar).
        return jsonify({"ok": True, "meta": meta})
    return redirect(url_for("account.conta"))


_ATUALIZAR_INVENTARIO_INTERVALO_S = 300


@bp.route("/conta/inventario/atualizar", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def atualizar_inventario():
    """"Atualizar agora": busca o inventário a pedido da pessoa (ação
    explícita, como o login). No máximo 1x a cada 5 min por conta, e
    nunca durante uma pausa pedida pela Steam (2026-11-15)."""
    from lodout import steam_api
    steamid = session["steamid"]
    est = inventario.estado(steamid)
    if est.get("em_andamento"):
        pass
    elif time.time() - float(est.get("ts") or 0) < _ATUALIZAR_INVENTARIO_INTERVALO_S:
        flash("Seu inventário acabou de ser atualizado. Dá para pedir de novo em alguns minutos.", "info")
    elif steam_api.em_cooldown("inventory"):
        flash("A Steam pediu uma pausa agora. O Lodout tenta de novo sozinho mais tarde.", "info")
    else:
        inventario.sincronizar_em_segundo_plano(steamid)
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def adicionar_posicao():
    steamid = session["steamid"]
    name = (request.form.get("name") or "").strip()
    if not name:
        flash("Informe o nome do item.", "error")
        return redirect(url_for("account.conta"))

    cost_raw = (request.form.get("cost") or "").strip()
    cost = None
    if cost_raw:
        try:
            cost = fmt.ler_reais(cost_raw)
        except ValueError:
            cost = None
        if cost is None or not math.isfinite(cost) or cost < 0:
            flash(
                "O custo precisa ser um número válido e igual ou maior que zero.",
                "error",
            )
            return redirect(url_for("account.conta"))

    quantity_raw = (request.form.get("quantity") or "").strip()
    try:
        quantity = int(quantity_raw) if quantity_raw else 1
    except ValueError:
        quantity = 0
    if quantity < 1:
        flash(
            "A quantidade precisa ser um número inteiro maior que zero.",
            "error",
        )
        return redirect(url_for("account.conta"))

    user_portfolio.add_position(steamid, name, cost, quantity)
    flash(f"{localize_name(name)} entrou na sua lista. Se aparecer “sem preço”, confira se o nome "
          "está igual ao do Mercado da Steam.", "success")
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/custo", methods=["POST"])
@rate_limited(CUSTO_MAX_HITS, CUSTO_WINDOW_S)
@login_required
@csrf_protect
def editar_custo(name: str):
    """Salva quanto a pessoa pagou. Pelo script da conta (Accept: JSON)
    devolve os números novos só desta linha -- sem recarregar a página
    inteira (conta-inventario.md, fase 3). Sem JavaScript, redireciona
    como sempre."""
    steamid = session["steamid"]
    quer_json = "application/json" in (request.headers.get("Accept") or "")
    # Aceita "35,10" além de "35.10" (teclado brasileiro).
    cost_raw = (request.form.get("cost") or "").strip()
    lote = (request.form.get("lote") or "").strip() or None
    erro = None
    # Campo apagado de propósito (limpar=1): o item volta a ficar sem valor
    # pago -- pra corrigir um valor errado ou desfazer (2026-11-15).
    if not cost_raw and request.form.get("limpar") == "1":
        user_portfolio.update_position_cost(steamid, name, None, lote=lote)
    if cost_raw:
        try:
            cost = fmt.ler_reais(cost_raw)
        except ValueError:
            cost = None
        if cost is None or not math.isfinite(cost) or cost < 0:
            erro = "O valor pago precisa ser um número igual ou maior que zero (ex.: 35,10)."
        else:
            user_portfolio.update_position_cost(steamid, name, cost, lote=lote)
    if quer_json:
        if erro:
            return jsonify({"ok": False, "erro": erro}), 400
        linhas = [p for p in user_portfolio.load_positions(steamid)
                  if p.get("name") == name and (not lote or p.get("lote") == lote)]
        if not linhas:
            # Tirado da lista em outra aba (ou pela sincronização) depois
            # que esta página abriu (revisão 2026-11-16).
            return jsonify({"ok": False, "recarregar": True, "erro":
                            "Este item não está mais na sua lista. "}), 404
        avaliacao = _formatar_linhas(
            portfolio.evaluate_portfolio(linhas, _preco_do_dia(linhas)),
            _meta_lucro(steamid))
        row = avaliacao["rows"][0]
        pnl = row.get("pnl") if row.get("has_cost") else None
        todas = user_portfolio.load_positions(steamid)
        totais = _textos_totais(_formatar_linhas(
            portfolio.evaluate_portfolio(todas, _preco_do_dia(todas)))["totals"])
        return jsonify({
            "ok": True,
            "totais": totais,
            "empate_fmt": row.get("empate_fmt"),
            "alvo_fmt": row.get("alvo_fmt"),
            "lucro_fmt": row.get("pnl_fmt") if pnl is not None else None,
            "lucro_pct_fmt": row.get("pnl_pct_fmt") or "",
            "empate": round(row["empate"], 4) if row.get("empate") else None,
            "confira": row.get("confira") or "",
            "lucro": round(pnl, 4) if pnl is not None else None,
            "lucro_classe": ("valor-positivo" if pnl and pnl > 0 else
                             "valor-negativo" if pnl and pnl < 0 else ""),
        })
    if erro:
        flash(erro, "error")
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/remover", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def remover_posicao(name: str):
    steamid = session["steamid"]
    lote = (request.form.get("lote") or "").strip() or None
    user_portfolio.remove_position(steamid, name, lote=lote)
    # Confirmação depois de remover (revisão 2026-11-16: a página só
    # recarregava, sem dizer nada).
    flash(f"{localize_name(name)} saiu da sua lista. "
          "Se ainda estiver no seu inventário da Steam, volta na próxima atualização.", "success")
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/anunciado", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def marcar_anunciado(name: str):
    """Item fora do inventário: "Está anunciado no Mercado" (caixa de
    marcar). Fica na conta até a pessoa marcar "Vendi" ou remover
    (pedido do usuário, 16/11)."""
    steamid = session["steamid"]
    lote = (request.form.get("lote") or "").strip() or None
    anunciado = request.form.get("anunciado") == "1"
    if user_portfolio.marcar_anunciado(steamid, name, anunciado, lote=lote):
        flash(f"{localize_name(name)}: " + (
            "marcado como anunciado no Mercado. Quando vender, marque “Vendi”."
            if anunciado else "não está mais marcado como anunciado."), "success")
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/vendido", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def marcar_vendido(name: str):
    """"Vendi": o item vai para "Itens vendidos", na página Histórico, com
    quanto a pessoa pagou e por quanto vendeu, e sai da lista (pedido do
    usuário, 16/11; "Meus trades" são as trocas)."""
    steamid = session["steamid"]
    lote = (request.form.get("lote") or "").strip() or None
    try:
        preco = fmt.ler_reais(request.form.get("sell_price"))
    except ValueError:
        preco = None
    try:
        quantidade = int((request.form.get("quantidade") or "1").strip())
    except ValueError:
        quantidade = 0
    if preco is None or not math.isfinite(preco) or preco <= 0:
        flash("Informe por quanto vendeu (o valor que o comprador pagou, ex.: 35,10).", "error")
        return redirect(url_for("account.conta"))
    vendido = user_portfolio.tirar_vendidas(steamid, name, quantidade, lote=lote)
    if vendido is None:
        flash("Não deu para marcar como vendido: confira a quantidade e se o item "
              "tem o valor pago.", "error")
        return redirect(url_for("account.conta"))
    venda = user_vendidos.adicionar(steamid, name, float(vendido["cost"]), preco, quantidade)
    pnl = venda.get("pnl") or 0
    resultado = (f"lucro de {fmt.brl(pnl)}" if pnl > 0 else
                 f"prejuízo de {fmt.brl(-pnl)}" if pnl < 0 else "sem lucro nem prejuízo")
    flash(f"{localize_name(name)} foi para “Itens vendidos”, no Histórico: vendido por {fmt.brl(preco)}"
          f"{' cada' if quantidade > 1 else ''}, {resultado} depois da taxa.", "success")
    return redirect(url_for("account.conta"))


# Até 16/11, anunciar no Mercado apagava o item e o valor pago (a
# sincronização achava que tinha vendido). Os backups diários guardam 7
# dias: até lá, a própria pessoa pode recuperar os dela pela conta, sem
# ninguém precisar entrar no servidor (pedido do usuário, 16/11).
RECUPERAR_ATE_TS = 1795392000.0  # 2026-11-23 21:00 UTC


@bp.route("/conta/recuperar", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def recuperar_apagados():
    from lodout.public_site import recuperar_posicoes
    steamid = session["steamid"]
    backups = recuperar_posicoes._backups()
    atuais = user_portfolio.load_positions(steamid)
    agora = time.time()
    novas, relatorio = recuperar_posicoes.planejar(steamid, atuais, backups, agora)
    voltaram = [r for r in relatorio if not r["acao"].startswith("conferir")]
    conferir = [r for r in relatorio if r["acao"].startswith("conferir")]
    if not voltaram:
        flash("Nada para recuperar: nenhum item com valor pago sumiu da sua lista "
              "nos últimos dias." + (" Confira à mão: " + ", ".join(
                  localize_name(r["item"]) for r in conferir) + "." if conferir else ""), "info")
        return redirect(url_for("account.conta"))
    copia = Path(_paths.DATA_DIR) / "backups" / time.strftime(
        f"recuperacao-{steamid}-%Y%m%d-%H%M%S.json", time.gmtime(agora))
    _paths.atomic_write_text(copia, json.dumps(atuais, ensure_ascii=False))
    user_store.save_user_json(steamid, "portfolio", novas)
    nomes = ", ".join(localize_name(r["item"]) for r in voltaram)
    flash(f"Voltaram com o valor pago: {nomes}. Marque “Está anunciado” ou “Vendi” em cada um."
          + (" Confira à mão: " + ", ".join(localize_name(r["item"]) for r in conferir) + "."
             if conferir else ""), "success")
    return redirect(url_for("account.conta"))


def _celula_csv(valor) -> str:
    """Texto seguro pra planilha: nome que começa com = + - @ viraria
    fórmula no Excel (injeção de CSV), então ganha um apóstrofo."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


def _num_csv(v) -> str:
    """Número com vírgula decimal (planilha em português)."""
    return "" if v is None else f"{v:.2f}".replace(".", ",")


@bp.route("/conta/tabela.csv")
@login_required
def exportar_tabela():
    """A tabela da conta como planilha (.csv), com os mesmos números da
    tela. Separador ";" e vírgula decimal, como o Excel em português
    espera; BOM pra acentos abrirem certos (2026-11-15)."""
    import csv
    import io
    steamid = session["steamid"]
    positions = user_portfolio.load_positions(steamid)
    meta = _meta_lucro(steamid)
    avaliacao = portfolio.evaluate_portfolio(positions, _preco_do_dia(positions))
    _marcar_lotes(avaliacao["rows"], positions)
    avaliacao = _formatar_linhas(avaliacao, meta)
    saida = io.StringIO()
    escritor = csv.writer(saida, delimiter=";", lineterminator="\r\n")
    escritor.writerow([
        "Item", "Nome na Steam", "Quantidade", "Lote",
        "Você pagou (cada)", "Vale hoje (cada)", "Vale hoje (total)",
        "Lucro se vender hoje", "Lucro (%)",
        "Venda sem prejuízo (cada)", f"Venda para lucrar {meta}% (cada)",
        "Situação"])
    for r in avaliacao["rows"]:
        custo = r.get("cost") if r.get("has_cost") else None
        empate = portfolio.break_even_price(custo) if custo else None
        qtd = r.get("quantity") or 1
        escritor.writerow([
            _celula_csv(r.get("name_fmt")), _celula_csv(r.get("name")), qtd,
            r.get("lote_numero") if (r.get("lotes_total") or 1) > 1 else "",
            _num_csv(custo), _num_csv(r.get("price")),
            _num_csv(r["price"] * qtd if r.get("price") is not None else None),
            _num_csv(r.get("pnl") if custo is not None else None),
            _num_csv(r.get("pnl_pct") if custo else None),
            _num_csv(empate), _num_csv(empate * (1 + meta / 100) if empate else None),
            # Revisão 30 (16/11): anunciado / fora do inventário.
            ("anunciado no Mercado" if r.get("anunciado") else
             f"fora do inventário desde {r['fora_quando']}" if r.get("fora_desde") else
             "no inventário" if r.get("origem") == inventario.SOURCE_STEAM else
             "adicionado à mão"),
        ])
    nome = time.strftime("lodout-conta-%Y-%m-%d.csv", time.gmtime())
    resp = make_response("\ufeff" + saida.getvalue())
    resp.headers["Content-Type"] = "text/csv; charset=utf-8"
    resp.headers["Content-Disposition"] = f'attachment; filename="{nome}"'
    resp.headers["Cache-Control"] = "no-store"
    return resp


@bp.route("/conta/exportar")
@login_required
def exportar_dados():
    """JSON com todo dado pessoal ligado a essa conta -- LGPD/direito de
    portabilidade: o usuário não deveria precisar pedir pra ninguém pra
    ter uma cópia do que o Lodout guarda sobre ele."""
    steamid = session["steamid"]
    usuario = user_store.get_user(steamid)
    resp = jsonify({
        "exportado_em": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "usuario": usuario,
        "portfolio": user_portfolio.load_positions(steamid),
        "trades": user_trades.load_trades(steamid),
        "watchlist": user_watchlist.load_items(steamid),
        "historico_valor": user_history.load_history(steamid),
        "vendidos": user_vendidos.load(steamid),
        "preferencias": user_store.load_user_json(steamid, "preferencias", {}),
    })
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="lodout-dados-{steamid}.json"')
    return resp


@bp.route("/conta/excluir")
@login_required
def excluir_confirmar():
    """Tela de confirmação -- a exclusão em si é só na rota POST abaixo.
    Página própria (não um `confirm()` de JS) porque o site não usa
    JavaScript em nenhuma outra tela."""
    return render_template("conta_excluir.html", csrf_token=csrf_token())


@bp.route("/conta/excluir", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def excluir():
    """Apaga a conta e todo dado pessoal (portfólio/trades/watchlist/
    histórico) -- irreversível. Ver `user_store.delete_user`."""
    steamid = session["steamid"]
    user_store.delete_user(steamid)
    apagar_perfil_cache(steamid)
    session.clear()
    # Confirmação na página inicial (antes não dizia nada).
    flash("Sua conta no Lodout foi excluída, com todos os seus dados.", "success")
    return redirect(url_for("index"))
