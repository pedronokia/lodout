"""Gráfico de linha em SVG, gerado no servidor sem dependência de charting."""
from __future__ import annotations

from xml.sax.saxutils import escape as _xml_escape


def line_chart_svg(series: "list[dict]", width: int = 640, height: int = 160,
                   padding: int = 12, css_class: str = "grafico-historico",
                   area_fill: bool = False,
                   rotulos: "list[str] | None" = None) -> str:
    """SVG de linha a partir de uma série [{ts, total}].

    "" se a série tiver menos de 2 pontos -- nada pra traçar uma linha.
    Os números são sempre formatados por este módulo (nunca interpolados
    de texto externo), então o SVG resultante é seguro pra embutir direto
    no template com `|safe`. `css_class` troca o estilo (ex. sparkline
    pequeno inline numa linha de tabela vs. gráfico grande de página).

    `area_fill=True` acrescenta um preenchimento em gradiente (cor atual,
    opaco no topo até transparente embaixo) sob a linha -- achado
    2026-11-03 (revisão de direção visual): uma linha nua sem contexto
    "parece wireframe". Só pro gráfico grande da página do item; os
    sparklines pequenos da tabela continuam sem fill de propósito (ruído
    visual nesse tamanho).

    `rotulos` (mesmo tamanho de `series`, opcional): um círculo
    transparente por ponto, com `<title>` nativo do SVG -- tooltip ao
    passar o mouse, sem JS nenhum (o CSP do site, `style-src 'self'`
    sem inline, bloqueia até `elemento.style.x = ...` via JS, não só o
    atributo `style=""`; posicionar um tooltip flutuante exigiria
    estilo inline de um jeito ou de outro). `fill="transparent"` (não
    `"none"`) de propósito -- `none` não captura clique/hover nenhum.
    """
    valores = [p["total"] for p in series]
    if len(valores) < 2:
        return ""
    minimo = min(valores)
    maximo = max(valores)
    span = maximo - minimo or 1.0
    n = len(valores)

    def _x(i: int) -> float:
        return padding + (i / (n - 1)) * (width - 2 * padding)

    def _y(v: float) -> float:
        # SVG: y cresce pra baixo -- inverte pro maior valor ficar em cima.
        return padding + (1 - (v - minimo) / span) * (height - 2 * padding)

    pontos = " ".join(
        f"{_x(i):.1f},{_y(v):.1f}" for i, v in enumerate(valores))

    defs_svg = ""
    area_svg = ""
    if area_fill:
        base = height - padding
        area_pontos = f"{_x(0):.1f},{base:.1f} {pontos} {_x(n - 1):.1f},{base:.1f}"
        grad_id = f"preenchimento-{css_class}"
        defs_svg = (
            f'<defs><linearGradient id="{grad_id}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="currentColor" stop-opacity="0.25"/>'
            f'<stop offset="100%" stop-color="currentColor" stop-opacity="0"/>'
            f'</linearGradient></defs>'
        )
        area_svg = f'<polygon points="{area_pontos}" fill="url(#{grad_id})"/>'

    pontos_svg = ""
    if rotulos and len(rotulos) == n:
        pontos_svg = "".join(
            f'<circle cx="{_x(i):.1f}" cy="{_y(v):.1f}" r="7" '
            f'fill="transparent" class="grafico-ponto-interativo" '
            f'data-info="{_xml_escape(rotulo)}" data-cx="{_x(i):.1f}" data-cy="{_y(v):.1f}" '
            f'data-val="{v:.2f}" data-idx="{i}">'
            f'<title>{_xml_escape(rotulo)}</title></circle>'
            for i, (v, rotulo) in enumerate(zip(valores, rotulos)))

    return (
        f'<svg viewBox="0 0 {width} {height}" class="{css_class}" '
        f'preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">'
        f'{defs_svg}{area_svg}'
        f'<polyline points="{pontos}" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>'
        f'{pontos_svg}'
        f'</svg>'
    )


def bar_chart_svg(valores: "list[float]", dias: "list[str]",
                  titulos: "list[str] | None" = None, width: int = 640,
                  height: int = 180, css_class: str = "grafico-barras") -> str:
    """Barras verticais com o dia embaixo e o valor em cima (contagens
    por dia, como as visitas do /status -- revisão 20/11).

    "" se não houver ao menos 2 valores. Com muitas barras, só parte dos
    dias e dos valores ganha rótulo (até ~8 de cada), para não encavalar.
    Sem `preserveAspectRatio="none"`: o texto não pode esticar. Os números
    são formatados aqui e os textos escapados, então é seguro com `|safe`.
    """
    n = len(valores)
    if n < 2 or len(dias) != n:
        return ""
    topo, base_txt, lado = 20, 22, 4
    area_h = height - topo - base_txt
    maximo = max(valores) or 1
    passo = (width - 2 * lado) / n
    largura = max(2.0, passo * 0.68)
    a_cada = max(1, -(-n // 8))
    titulos = titulos if titulos and len(titulos) == n else None
    partes = []
    for i, v in enumerate(valores):
        h = max(1.0, (v / maximo) * area_h) if v else 0.0
        x = lado + i * passo + (passo - largura) / 2
        y = topo + area_h - h
        cx = x + largura / 2
        # O último dia sempre ganha rótulo; o rótulo regular logo antes
        # dele sai se ficar perto demais (27/11: "26/11" e "27/11" se
        # sobrepunham no fim do gráfico de visitas).
        rotular = i == n - 1 or (i % a_cada == 0 and (n - 1 - i) * 2 >= a_cada)
        titulo = f"<title>{_xml_escape(titulos[i])}</title>" if titulos else ""
        valor_txt = (
            f'<text x="{cx:.1f}" y="{y - 5:.1f}" text-anchor="middle" '
            f'class="barra-valor">{int(round(v))}</text>'
            if rotular else "")
        dia_txt = (
            f'<text x="{cx:.1f}" y="{height - 6:.1f}" text-anchor="middle" '
            f'class="barra-dia">{_xml_escape(dias[i])}</text>'
            if rotular else "")
        partes.append(
            f'<g class="barra-grupo">{titulo}'
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{largura:.1f}" height="{h:.1f}" '
            f'rx="2" class="barra"/>{valor_txt}{dia_txt}</g>')
    linha_base = (f'<line x1="{lado}" y1="{topo + area_h + 0.5:.1f}" '
                  f'x2="{width - lado}" y2="{topo + area_h + 0.5:.1f}" class="barra-base"/>')
    return (
        f'<svg viewBox="0 0 {width} {height}" class="{css_class}" role="img" '
        f'aria-label="Gráfico de barras" xmlns="http://www.w3.org/2000/svg">'
        f'{linha_base}{"".join(partes)}</svg>')
