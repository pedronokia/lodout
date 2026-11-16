"""Blueprint do histórico pessoal -- `/conta/historico`.

O ponto é gravado em `account.py:conta()` (toda visita a `/conta`
registra o valor atual, com dedup -- ver `user_history.
record_if_changed`). Esta tela exibe a série já guardada e, desde 16/11,
os itens que a pessoa marcou como vendidos na conta (`user_vendidos`).
"""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, session, url_for

from lodout.localization import localize_name
from lodout.public_site import charts, fmt, user_history, user_vendidos
from lodout.public_site.auth import csrf_protect, csrf_token, login_required
from lodout.public_site.rate_limit import (
    MUTATION_MAX_HITS, MUTATION_WINDOW_S, rate_limited,
)

bp = Blueprint("history", __name__)


@bp.route("/conta/historico")
@login_required
def listar():
    steamid = session["steamid"]
    # Em ordem de data (o arquivo é gravado na ordem das visitas, que
    # normalmente já é essa; ordenar deixa a tabela e o gráfico certos
    # mesmo se não for).
    series = sorted(user_history.load_history(steamid),
                    key=lambda p: p.get("ts") or 0)
    pontos = [
        {"data": fmt.data_hora_br(p["ts"]), "total_fmt": fmt.brl(p["total"])}
        for p in series
    ]
    pontos.reverse()

    valores = [p["total"] for p in series]
    # Mesmo padrão do gráfico de preço em /item/<name>: tooltip por ponto
    # (data + valor exato) e legenda com o range real, já que a linha
    # sozinha é normalizada entre o mínimo e o máximo da série -- sem
    # isso, uma variação de R$1 e uma de R$1000 desenham a mesma
    # inclinação, e leitor de tela não tem texto associado ao SVG.
    rotulos = [f"{fmt.data_hora_br(p['ts'])} — {fmt.brl(p['total'])}"
               for p in series]
    grafico_tendencia = None
    if len(valores) >= 2:
        if valores[-1] > valores[0]:
            grafico_tendencia = "alta"
        elif valores[-1] < valores[0]:
            grafico_tendencia = "baixa"
    grafico_legenda = (
        f"{fmt.brl(min(valores))} – {fmt.brl(max(valores))} no período"
        if len(valores) >= 2 else None)

    vendidos = []
    for i, v in enumerate(user_vendidos.load(steamid)):
        pnl = v.get("pnl") or 0
        vendidos.append({
            "index": i,
            "nome": localize_name(v.get("name") or ""),
            "nome_steam": v.get("name") or "",
            "quantidade": int(v.get("quantity") or 1),
            "data": fmt.data_hora_br(v.get("sell_ts") or 0)[:10],
            "pagou_fmt": fmt.brl(v.get("buy_cost")),
            "vendeu_fmt": fmt.brl(v.get("sell_price")),
            "recebeu_fmt": fmt.brl(v.get("net_received")),
            "lucro_fmt": ("+" if pnl > 0 else "") + fmt.brl(pnl),
            "lucro_classe": "valor-positivo" if pnl > 0 else "valor-negativo" if pnl < 0 else "",
            "ts": v.get("sell_ts") or 0,
        })
    vendidos.sort(key=lambda v: -v["ts"])
    total_vendidos = sum(v.get("pnl") or 0 for v in user_vendidos.load(steamid))

    return render_template(
        "conta_historico.html",
        vendidos=vendidos,
        vendidos_total_fmt=("+" if total_vendidos > 0 else "") + fmt.brl(total_vendidos),
        vendidos_total_classe=("valor-positivo" if total_vendidos > 0 else
                               "valor-negativo" if total_vendidos < 0 else ""),
        csrf_token=csrf_token(),
        grafico=charts.line_chart_svg(series, area_fill=True, rotulos=rotulos),
        grafico_tendencia=grafico_tendencia,
        grafico_legenda=grafico_legenda,
        pontos=pontos,
    )


@bp.route("/conta/historico/vendidos/<int:index>/remover", methods=["POST"])
@rate_limited(MUTATION_MAX_HITS, MUTATION_WINDOW_S)
@login_required
@csrf_protect
def remover_vendido(index: int):
    """Apaga o registro de uma venda (marcada por engano, por exemplo)."""
    tirado = user_vendidos.remover(session["steamid"], index)
    if tirado:
        flash(f"A venda de {localize_name(tirado.get('name') or '')} saiu do histórico.", "success")
    return redirect(url_for("history.listar"))
