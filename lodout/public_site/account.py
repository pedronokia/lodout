"""Blueprint de conta: "Entrar com Steam" + portfólio pessoal.

O dashboard público (`server.py`/`index.html`) continua anônimo e sem
conta, como na Fase 1 -- isto aqui é opcional, só pra quem quiser
acompanhar a própria carteira.
"""
from __future__ import annotations

import math
import secrets
import time
import urllib.parse

from flask import (
    Blueprint, flash, jsonify, redirect, render_template, request,
    send_file, session, url_for,
)

from lodout import portfolio, scan_store
from lodout.localization import localize_name
from lodout.prices import PriceCache
from lodout.public_site import (
    catalogo, fmt, inventario, raridade, steam_openid, user_history, user_portfolio,
    user_store, user_trades, user_watchlist,
)
from lodout.public_site.auth import csrf_protect, csrf_token, login_required
from lodout.public_site.rate_limit import (
    LOGIN_MAX_HITS, LOGIN_WINDOW_S, MUTATION_MAX_HITS, MUTATION_WINDOW_S,
    rate_limited,
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


def _preco_do_dia(positions: "list[dict]"):
    """Preço de cada item da conta: o da coleta com nota quando existe;
    senão o do catálogo amplo (todo o Mercado, 1x por dia). Só leitura
    local, sem rede (catalogo-grande.md, fase 2)."""
    cache = PriceCache()
    do_catalogo = catalogo.precos([p.get("name") for p in positions])

    def _preco(nome: str):
        preco = cache.get(nome)
        return preco if preco is not None else do_catalogo.get(nome)
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
    for row in avaliacao["rows"]:
        custo = row.get("cost") or 0
        if row.get("has_cost") and custo > 0:
            empate = portfolio.break_even_price(custo)
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
        row["price_fmt"] = fmt.brl(row.get("price"))
        if row.get("price") is not None:
            row["valor_total_fmt"] = fmt.brl(row["price"] * (row.get("quantity") or 1))
        row["cost_fmt"] = fmt.brl(row.get("cost"))
        row["pnl_fmt"] = fmt.brl(row.get("pnl"))
        row["score"] = raw.get("score") if raw else None
        # Item do inventário fora da coleta: a imagem vem do próprio
        # inventário (hash do CDN da Steam), em vez de ficar sem foto.
        row.update(raridade.icone_raridade(raw or {"icon": row.get("icon")}))
    t = avaliacao["totals"]
    t["cost_fmt"] = fmt.brl(t.get("cost"))
    t["cost_known_fmt"] = fmt.brl(t.get("cost_known"))
    t["market_fmt"] = fmt.brl(t.get("market"))
    t["net_if_sold_fmt"] = fmt.brl(t.get("net_if_sold"))
    t["pnl_fmt"] = fmt.brl(t.get("pnl"))
    avaliacao["textos"] = _textos_totais(t)
    return avaliacao


def _textos_totais(t: dict) -> dict:
    """Textos dos cartões do topo e do aviso de itens sem valor pago.
    A página e a resposta JSON de "salvar valor pago" usam os mesmos,
    pra o topo atualizar sem recarregar e sem divergir do servidor."""
    n, com = t.get("positions") or 0, t.get("known_cost") or 0
    sem = t.get("unknown_cost") or 0
    pnl, pct = t.get("pnl"), t.get("pnl_pct")
    if pnl is None:
        lucro_sub = "informe o valor pago para ver"
    elif pct is None:
        lucro_sub = "dos itens com o valor pago"
    else:
        sinal = "+" if pct > 0.05 else ("\u2212" if pct < -0.05 else "")
        lucro_sub = f"{sinal}{fmt.pct(abs(pct))}% do que você pagou"
    if sem:
        aviso = (f"{sem} {'item está' if sem == 1 else 'itens estão'} sem o "
                 "valor pago. Preencha para ver por quanto vender e para "
                 f"{'ele entrar' if sem == 1 else 'eles entrarem'} no lucro.")
    else:
        aviso = ""
    return {
        "valor": t.get("market_fmt") or fmt.brl(t.get("market")),
        "valor_sub": f"{n} {'item' if n == 1 else 'itens'}",
        "liquido": t.get("net_if_sold_fmt") or fmt.brl(t.get("net_if_sold")),
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
    session.pop("steamid", None)
    return redirect(url_for("index"))


@bp.route("/conta")
@login_required
def conta():
    steamid = session["steamid"]
    positions = user_portfolio.load_positions(steamid)
    # Preço vem do mesmo cache compartilhado da Fase 1 -- leitura pura,
    # sem rede. Se o item nunca foi escaneado, a linha some sem preço
    # quando a Steam não respondeu).
    avaliacao_bruta = portfolio.evaluate_portfolio(
        positions, _preco_do_dia(positions))
    # Grava o ponto de histórico ANTES de formatar -- precisa do valor
    # numérico (totals.market), não do "_fmt" em string. Dedup embutido:
    # visitar /conta duas vezes seguidas sem nada mudar não dobra a série.
    user_history.record_if_changed(steamid, avaliacao_bruta["totals"]["market"])
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
        taxa_steam_pct=round(portfolio.STEAM_FEE * 100),
    )


def _marcar_lotes(rows: "list[dict]", positions: "list[dict]") -> None:
    """Leva o id do lote de cada posição para a linha (mesma ordem: uma
    linha por posição) e numera os lotes do mesmo item ("lote 1 de 2")."""
    total: dict = {}
    for pos in positions:
        total[pos.get("name")] = total.get(pos.get("name"), 0) + 1
    visto: dict = {}
    for row, pos in zip(rows, positions):
        row["lote"] = pos.get("lote")
        n = total.get(pos.get("name"), 1)
        visto[pos.get("name")] = visto.get(pos.get("name"), 0) + 1
        row["lotes_total"] = n
        row["lote_numero"] = visto[pos.get("name")]


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
              "(ou de nenhum): juntar com um lote sem valor inventaria um preço.", "error")
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
    if not 1 <= meta <= _META_LUCRO_MAX:
        flash(f"A meta de lucro precisa ser um número entre 1 e {_META_LUCRO_MAX}.",
              "error")
        return redirect(url_for("account.conta"))
    prefs = user_store.load_user_json(steamid, "preferencias", {}) or {}
    prefs["meta_lucro_pct"] = meta
    user_store.save_user_json(steamid, "preferencias", prefs)
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

    cost_raw = (request.form.get("cost") or "").strip().replace(",", ".")
    cost = None
    if cost_raw:
        try:
            cost = float(cost_raw)
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
    return redirect(url_for("account.conta"))


@bp.route("/conta/posicoes/<name>/custo", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
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
    cost_raw = (request.form.get("cost") or "").strip().replace(",", ".")
    lote = (request.form.get("lote") or "").strip() or None
    erro = None
    if cost_raw:
        try:
            cost = float(cost_raw)
        except ValueError:
            cost = None
        if cost is None or not math.isfinite(cost) or cost < 0:
            erro = "O valor pago precisa ser um número igual ou maior que zero."
        else:
            user_portfolio.update_position_cost(steamid, name, cost, lote=lote)
    if quer_json:
        if erro:
            return jsonify({"ok": False, "erro": erro}), 400
        linhas = [p for p in user_portfolio.load_positions(steamid)
                  if p.get("name") == name and (not lote or p.get("lote") == lote)]
        if not linhas:
            return jsonify({"ok": False, "erro": "Item não encontrado."}), 404
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
    return redirect(url_for("account.conta"))


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
    return redirect(url_for("index"))
