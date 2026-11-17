"""Blueprint de "Meus trades" -- `/conta/trades`.

Desde 17/11 (pedido do usuário) são TROCAS entre jogadores: o que a
pessoa deu, o que recebeu e quanto valia cada lado no dia
(`user_trocas.py`). Vendas ficam em "Itens vendidos", no Histórico; os
registros antigos de compra e venda que existiam aqui vão para lá na
primeira visita (`user_trocas.migrar_trades_antigos`).
"""
from __future__ import annotations

import datetime
import math

from flask import (
    Blueprint, flash, redirect, render_template, request, session, url_for,
)

from lodout import scan_store
from lodout.localization import localize_name
from lodout.public_site import fmt, raridade, user_trocas
from lodout.public_site.auth import csrf_protect, csrf_token, login_required
from lodout.public_site.rate_limit import (
    MUTATION_MAX_HITS, MUTATION_WINDOW_S, rate_limited,
)

bp = Blueprint("trades", __name__)

_LINHAS_SEM_JS = 3      # linhas por lado no formulário (o JS adiciona mais)
_VALOR_MAX = 1_000_000  # R$ por unidade; acima disso é erro de digitação
_QTD_MAX = 1000


def _scan_lookup() -> dict:
    scan = scan_store.load_last_scan()
    if not scan:
        return {}
    return {r["name"]: r for r in scan["results"]}


def _avisar_migracao(steamid: str) -> None:
    movidos = user_trocas.migrar_trades_antigos(steamid)
    if movidos:
        flash(f"{'1 registro' if movidos == 1 else f'{movidos} registros'} de compra e venda "
              f"que {'estava' if movidos == 1 else 'estavam'} aqui "
              f"{'foi' if movidos == 1 else 'foram'} para “Itens vendidos”, no Histórico. "
              "“Meus trades” agora guarda as suas trocas com outros jogadores.", "info")


def _formatar(registros: "list[dict]") -> "tuple[list[dict], dict]":
    from lodout.public_site.account import _preco_do_dia
    nomes = sorted({i["name"] for t in registros for lado in ("deu", "recebeu")
                    for i in t.get(lado) or [] if i.get("name")})
    preco_hoje = _preco_do_dia([{"name": n} for n in nomes])
    icones = raridade.completar_com_catalogo(_scan_lookup(), nomes)
    saldo_dia = 0.0
    saldo_hoje = 0.0
    trocas_com_hoje = 0
    linhas = []
    for idx, t in enumerate(registros):
        lados = {}
        hoje_completo = True
        for lado in ("deu", "recebeu"):
            itens = []
            soma_hoje = 0.0
            for i in t.get(lado) or []:
                qtd = int(i.get("quantity") or 1)
                p = preco_hoje(i["name"])
                if p is None:
                    hoje_completo = False
                else:
                    soma_hoje += qtd * p
                itens.append({
                    "name": i["name"], "name_fmt": localize_name(i["name"]),
                    "quantidade": qtd, "valor_fmt": fmt.brl(i.get("valor")),
                    **raridade.icone_raridade(icones.get(i["name"])),
                })
            lados[lado] = {"itens": itens, "total": user_trocas.total(t.get(lado)),
                           "hoje": round(soma_hoje, 2)}
        saldo = round(lados["recebeu"]["total"] - lados["deu"]["total"], 2)
        saldo_dia += saldo
        hoje = None
        if hoje_completo:
            hoje = round(lados["recebeu"]["hoje"] - lados["deu"]["hoje"], 2)
            saldo_hoje += hoje
            trocas_com_hoje += 1
        linhas.append({
            "index": idx,
            "data": datetime.datetime.fromtimestamp(float(t.get("ts") or 0), tz=fmt.FUSO_BR).strftime("%d/%m/%Y"),
            "deu": lados["deu"], "recebeu": lados["recebeu"],
            "deu_total_fmt": fmt.brl(lados["deu"]["total"]),
            "recebeu_total_fmt": fmt.brl(lados["recebeu"]["total"]),
            "saldo": saldo, "saldo_fmt": ("+" if saldo > 0 else "") + fmt.brl(saldo),
            "hoje": hoje,
            "hoje_fmt": (("+" if hoje > 0 else "") + fmt.brl(hoje)) if hoje is not None else None,
            "deu_hoje_fmt": fmt.brl(lados["deu"]["hoje"]) if hoje is not None else None,
            "recebeu_hoje_fmt": fmt.brl(lados["recebeu"]["hoje"]) if hoje is not None else None,
            "notas": t.get("notas") or "",
            "descricao": " e ".join(i["name_fmt"] for i in lados["recebeu"]["itens"][:2]),
        })
    linhas.reverse()  # mais recente primeiro; `index` é o original
    resumo = {
        "n": len(registros),
        "saldo_dia": round(saldo_dia, 2),
        "saldo_dia_fmt": ("+" if saldo_dia > 0 else "") + fmt.brl(saldo_dia),
        "saldo_hoje": round(saldo_hoje, 2),
        "saldo_hoje_fmt": ("+" if saldo_hoje > 0 else "") + fmt.brl(saldo_hoje),
        "com_hoje": trocas_com_hoje,
    }
    return linhas, resumo


@bp.route("/conta/trades")
@login_required
def listar():
    steamid = session["steamid"]
    _avisar_migracao(steamid)
    linhas, resumo = _formatar(user_trocas.load(steamid))
    return render_template(
        "conta_trades.html", trocas=linhas, resumo=resumo,
        linhas_form=range(_LINHAS_SEM_JS), hoje=datetime.date.today().isoformat(),
        csrf_token=csrf_token(),
    )


def _ler_lado(prefixo: str) -> "tuple[list[dict], str | None]":
    """Itens de um lado do formulário ({prefixo}_nome/_qtd/_valor, uma
    entrada por linha). Linha sem nome é ignorada. (itens, erro)."""
    nomes = request.form.getlist(f"{prefixo}_nome")
    qtds = request.form.getlist(f"{prefixo}_qtd")
    valores = request.form.getlist(f"{prefixo}_valor")
    itens = []
    for i, nome in enumerate(nomes):
        nome = (nome or "").strip()
        if not nome:
            continue
        if len(nome) > 200:
            return [], "O nome de um item está longo demais."
        bruto_qtd = (qtds[i] if i < len(qtds) else "").strip()
        try:
            qtd = int(bruto_qtd) if bruto_qtd else 1
        except ValueError:
            qtd = 0
        if not 1 <= qtd <= _QTD_MAX:
            return [], f"Confira a quantidade de {localize_name(nome)} (um número de 1 a {_QTD_MAX})."
        try:
            valor = fmt.ler_reais(valores[i] if i < len(valores) else "")
        except ValueError:
            valor = None
        if valor is None or not math.isfinite(valor) or not 0 < valor <= _VALOR_MAX:
            return [], (f"Confira o valor de {localize_name(nome)}: quanto uma unidade valia no "
                        "dia da troca, em reais (ex.: 35,10).")
        itens.append({"name": nome, "quantity": qtd, "valor": round(valor, 2)})
    if len(itens) > user_trocas.MAX_ITENS_POR_LADO:
        return [], f"No máximo {user_trocas.MAX_ITENS_POR_LADO} itens de cada lado."
    return itens, None


def _ler_data() -> "tuple[float | None, str | None]":
    bruto = (request.form.get("data") or "").strip()
    if not bruto:
        return None, None
    try:
        dia = datetime.date.fromisoformat(bruto)
    except ValueError:
        return None, "Confira a data da troca."
    if dia > datetime.date.today() or dia.year < 2013:
        return None, "A data da troca precisa ser de hoje ou de antes."
    meio_dia = datetime.datetime.combine(dia, datetime.time(12), tzinfo=fmt.FUSO_BR)
    return meio_dia.timestamp(), None


@bp.route("/conta/trades", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def adicionar():
    steamid = session["steamid"]
    deu, erro = _ler_lado("deu")
    if not erro:
        recebeu, erro = _ler_lado("recebeu")
    if not erro and (not deu or not recebeu):
        erro = "Informe pelo menos um item que você deu e um que recebeu."
    ts, erro_data = _ler_data()
    erro = erro or erro_data
    if erro:
        flash(erro + " Nada foi registrado.", "error")
        return redirect(url_for("trades.listar"))
    troca = user_trocas.adicionar(steamid, deu, recebeu,
                                  notas=(request.form.get("notas") or "").strip(), ts=ts)
    saldo = round(user_trocas.total(troca["recebeu"]) - user_trocas.total(troca["deu"]), 2)
    resultado = (f"você recebeu {fmt.brl(saldo)} a mais em valor" if saldo > 0 else
                 f"você deu {fmt.brl(-saldo)} a mais em valor" if saldo < 0 else
                 "os dois lados valiam o mesmo")
    flash(f"Troca registrada: {resultado}, pelos valores do dia.", "success")
    return redirect(url_for("trades.listar"))


@bp.route("/conta/trades/<int:index>/remover", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def remover(index: int):
    if user_trocas.remover(session["steamid"], index):
        flash("A troca saiu da sua lista.", "success")
    return redirect(url_for("trades.listar"))
