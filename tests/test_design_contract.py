"""Contrato de design do site público -- trava os tokens da identidade
OpenCode lendo `style.css` do disco (sem navegador, roda na suíte normal).

A regressão visual (`tests/visual/visual_regression.py`) pega MUDANÇAS
de renderização; este teste pega mudanças de FONTE -- alguém trocar
`--accent`, o corpo de 17px, o raio dos cards etc. e não perceber. Se
um token mudar de propósito, o teste muda junto: é o documento vivo da
identidade visual (valores conferidos com opencode.ai/brand em 2026-11-12).
"""
from __future__ import annotations

import re
from pathlib import Path

STYLE = (
    Path(__file__).resolve().parents[1]
    / "lodout" / "public_site" / "static" / "style.css"
)


def _css() -> str:
    return STYLE.read_text(encoding="utf-8")


def _bloco(css: str, seletor: str) -> str:
    """Texto da PRIMEIRA regra `seletor { ... }` (do abre-chaves ao
    primeiro fecha-chaves). Suficiente para regras simples da folha --
    blocos com @media aninhado não passam por aqui."""
    início = css.find(f"{seletor} {{")
    assert início >= 0, f"regra não encontrada: {seletor}"
    fim = css.find("}", início)
    return css[início:fim]


def test_tokens_de_superficie_opencode():
    css = _css()
    # PRETO #080808 (cabeçalho) + CINZA ESCURO #161616 (site): fundo #161616,
    # tiles #1e1e1e, texto #e8e8e8, texto secundário #b3b3b3 (contraste
    # 4.5:1 no hover #252525), bordas #333333.
    assert "--bg: #161616" in css
    assert "--bg-elevated: #1e1e1e" in css
    assert "--surface: #1e1e1e" in css
    assert "--surface-strong: #0a0a0a" in css
    assert "--surface-sunken: #131313" in css
    assert "--surface-escura: #161616" in css
    assert "--text: #e8e8e8" in css
    assert "--text-muted: #b3b3b3" in css
    assert "--border: #4a4a4a" in css


def test_laranja_da_casa():
    css = _css()
    # Laranja da casa (Claude Code): #f97316 nos botões/pílulas ativas (70%
    # opacidade = rgba(249, 115, 22, 0.7)) e hover #b8480a. Links: eram
    # #d0580c (4.5:1 no branco, do tema claro); no fundo escuro davam
    # 4,0:1 -- agora o próprio #f97316 (5,9:1 em --surface; auditoria de
    # acessibilidade com axe-core, 2026-11-14).
    assert "--accent: #f97316" in css
    assert "--accent-bright: #f97316" in css
    assert "--accent-hover: #b8480a" in css
    assert "background: rgba(184, 72, 10, 0.7);" in css
    # Foco de teclado e item ativo das barras escuras acompanham o laranja.
    assert "--focus: #f97316" in css
    assert "--chrome-foco: #fb923c" in css
    # Anel de foco dos formulários e selo "novo" acompanham o laranja.
    assert "rgba(249, 115, 22, 0.28)" in css
    assert "rgba(249, 115, 22, 0.1)" in css


def test_raios_da_apple():
    css = _css()
    # Pílula de 980px (botões/chips) e cards com raio 18px.
    assert "--radius-pill: 980px" in css
    assert "--radius-md: 18px" in css
    # A grade usa as medidas da Apple: 980px de conteúdo.
    assert "--largura-conteudo: 980px" in css
    # Pelo menos um botão/chip usa a pílula (não um raio menor).
    assert "border-radius: var(--radius-pill);" in css


def test_corpo_tipografico_17px():
    css = _css()
    assert "--fs-base: 1.0625rem" in css  # 17px
    corpo = _bloco(css, "body")
    assert "font-size: var(--fs-base);" in corpo
    # 25/17 ≈ 1.47 (25px de entrelinha em corpo de 17px).
    assert "line-height: 1.47;" in corpo
    # Espaçamento entre letras pelo tamanho de cada elemento (dynamic
    # metrics da Inter), não um valor fixo no body herdado por todo texto
    # menor -- isso espremia os rótulos de 12px (2026-11-15).
    assert "letter-spacing" not in corpo
    assert "letter-spacing: calc((1em - 12px) * -0.04);" in css
    assert "font-weight: 450;" in corpo


def test_fonte_inter_autohospedada():
    """A pilha começa pela Inter Variable auto-hospedada (webfont) --
    o site fica IGUAL em qualquer sistema. Contexto (2026-11-12): o
    endpoint de webfont da Apple só atende com Referer do próprio
    apple.com (hotlink testado: 404 fora dele) e a licença da SF Pro
    não permite self-host; Inter é a open source mais próxima."""
    css = _css()
    assert 'font-family: "Inter Variable";' in css
    assert "fonts/inter-latin-opsz-normal.woff2?v=1" in css
    assert 'format("woff2-variations");' in css
    assert "font-weight: 100 900;" in css
    assert "font-display: swap;" in css
    assert '--font-sans: "Inter Variable", "Inter", -apple-system,' in css


def test_arquivos_da_fonte_comitados():
    """Fonte e licença (SIL OFL 1.1) existem no repositório -- sem eles
    o site cai no fallback do sistema e volta a divergir entre
    computadores."""
    pasta = STYLE.parent / "fonts"
    fonte = pasta / "inter-latin-opsz-normal.woff2"
    assert fonte.is_file() and fonte.stat().st_size > 20_000
    assert fonte.read_bytes()[:4] == b"wOF2"
    licenca = (pasta / "OFL.txt").read_text(encoding="utf-8")
    assert "SIL OPEN FONT LICENSE" in licenca


def test_titulos_600_e_escala_32_48_64():
    css = _css()
    titulos = _bloco(css, "h1, h2, h3")
    assert "font-weight: 600;" in titulos
    assert "--fs-xl: 2rem" in css      # 32px
    assert "--fs-2xl: 3rem" in css     # 48px
    assert "--fs-display: 4rem" in css  # 64px


def test_rodape_cinza_claro_12px():
    css = _css()
    rodape = _bloco(css, "footer.rodape")
    # Faixa própria em --surface-sunken. Texto em --fs-xs desde o
    # redesenho de 2026-11-14 (12px ficava pequeno demais pro aviso).
    assert "background: var(--surface-sunken);" in rodape
    assert "font-size: var(--fs-xs);" in rodape
    # Marca e aviso à esquerda, links à direita, base embaixo.
    assert '"marca nav"' in rodape and '"base  base"' in rodape


def test_cards_sem_fio_com_elevacao_hover():
    css = _css()
    card = _bloco(css, ".cartao-item")
    # Card-tile: sem fio em repouso; elevação sutil (shadow-lg) + fio
    # laranja 35% no hover/focus. Transição suave, respeita reduced-motion.
    assert "border: 0;" in card
    assert "border-radius: var(--radius-md);" in card
    assert "transition: box-shadow var(--dur-emphasis) var(--ease-standard), border-color var(--dur-emphasis) var(--ease-standard);" in card
    assert "box-shadow: var(--shadow-lg);" in css
    assert "border: 1px solid rgba(249, 115, 22, 0.35);" in css
    # Brilho diagonal animado no hover/focus (reduced-motion o esconde).
    assert ".cartao-item-brilho {" in css
    assert "rgba(249, 115, 22, 0.12)" in css
    # Focus visível no card.
    assert ".cartao-item:focus-visible {" in css
    assert "outline: 2px solid var(--focus);" in css
    # Estado pressed.
    assert ".cartao-item:active {" in css
    assert "transform: scale(0.995);" in css


def test_pagina_branca_com_faixa_borda_a_borda():
    """A página inteira é o branco #ffffff e as seções grandes atravessam
    a tela de borda a borda (truque 100vw), com o conteúdo de volta na
    coluna dentro da faixa."""
    css = _css()
    assert "background: var(--bg);" in css  # body na página branca
    faixa = _bloco(css, ".faixa")
    assert "width: 100vw;" in faixa
    assert "margin-left: calc(50% - 50vw);" in faixa
    # O html corta o excedente do 100vw (barra de rolagem).
    html_bloco = _bloco(css, "html")
    assert "overflow-x: clip;" in html_bloco


def test_ficha_do_item_tile_branca():
    css = _css()
    ficha = _bloco(css, ".resumo-cards-item")
    # Painel de métricas vira tile branca na página cinza, com o selo
    # de Nota em caixinha cinza dentro (inverso do layout antigo).
    assert "background: var(--surface);" in ficha
    selo = _bloco(css, ".resumo-cards-item .card-nota-destaque")
    assert "background: var(--surface-strong);" in selo


def test_polimento_da_maquete_v4():
    """Rodada 2026-11-12: laranja como identidade + polimento aprovado
    na maquete v4 (pílulas, abas, faixa de informação, CTA do item e
    rodapé alinhado)."""
    css = _css()
    # Vitrine/Lista ativo ficou neutro em 2026-11-14 (o laranja fica só
    # na aba de categoria; dois controles laranja lado a lado disputavam).
    visao = _bloco(css, '.seletor-visao a[aria-current="page"]')
    assert "background: var(--surface-hover);" in visao
    assert "rgba(249, 115, 22" not in visao
    # Abas de categoria: fantasma (transparente + fio) quando inativas,
    # laranja na ativa.
    aba = _bloco(css, ".aba-categoria")
    assert "background: transparent;" in aba
    assert "border: 1px solid var(--border);" in aba
    aba_ativa = _bloco(css, '.aba-categoria[aria-current="page"]')
    # O laranja de ação virou token (auditoria 17/11), com o mesmo valor.
    assert "background: var(--accent-acao);" in aba_ativa
    assert "--accent-acao: rgba(249, 115, 22, 0.7);" in css
    # Estado da coleta na home: linha leve com bolinha de status (era a
    # caixa .painel-info com fios laranja, até 2026-11-14).
    linha = _bloco(css, ".status-coleta")
    assert "padding-left: 18px;" in linha and "font-size: var(--fs-sm);" in linha
    assert "background: var(--positive);" in _bloco(css, ".status-coleta-ponto")
    # CTA laranja da página do item, em pílula com texto branco (70% opacidade).
    acao = _bloco(css, ".botao-acao")
    assert "background: var(--accent-acao);" in acao
    assert "border-radius: var(--radius-pill);" in acao
    # Linha de coleta fechando a ficha do item (régua de baixo).
    coleta = _bloco(css, ".resumo-cards-item .card-coleta")
    assert "border-top: 1px solid var(--border);" in coleta
    # Aviso do rodapé em linha curta (não atravessa a largura toda).
    assert "max-width: 46ch;" in _bloco(css, ".rodape-marca p")


def test_respeita_reduced_motion():
    css = _css()
    assert "@media (prefers-reduced-motion: reduce)" in css


def test_sem_estilo_inline_no_css():
    """O CSP não permite estilos inline (AGENTS.md): a folha não pode
    nem ela mesma normalizar `style=""` em lugar nenhum."""
    css = _css()
    sem_comentarios = re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)
    assert not re.search(r'\bstyle\s*=\s*"', sem_comentarios)


# ── Contraste calculado (auditoria de acessibilidade, 2026-11-14) ──────
# Em vez de só fixar o hex, CALCULA o contraste WCAG de cada par texto ×
# fundo que o site usa de verdade. Se alguém trocar um token por um tom
# bonito mas ilegível (como os verdes/vermelhos de tema claro que ficaram
# meses no fundo escuro, ~3,2:1), este teste quebra com o par e o valor.

def _tokens(css: str) -> "dict[str, str]":
    raiz = css[css.index(":root {"):]
    raiz = raiz[:raiz.index("\n}")]
    return dict(re.findall(r"(--[\w-]+):\s*(#[0-9a-fA-F]{6})\b", raiz))


def _luminancia(hexcor: str) -> float:
    c = [int(hexcor[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def _contraste(a: str, b: str) -> float:
    la, lb = _luminancia(a), _luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def _mistura(frente: str, fundo: str, alfa: float) -> str:
    f = [int(frente[i:i + 2], 16) for i in (1, 3, 5)]
    g = [int(fundo[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(f[k] * alfa + g[k] * (1 - alfa)):02x}" for k in range(3))


def test_contraste_dos_textos_sobre_os_fundos():
    t = _tokens(_css())
    fundos = ["--bg", "--surface", "--surface-hover"]
    textos = ["--text", "--text-muted", "--text-bright", "--accent-bright",
              "--positive", "--warn", "--danger"]
    ruins = []
    for tx in textos:
        for fd in fundos:
            r = _contraste(t[tx], t[fd])
            if r < 4.5:
                ruins.append(f"{tx} {t[tx]} sobre {fd} {t[fd]}: {r:.2f}:1")
    assert not ruins, "texto abaixo de 4,5:1 -> " + "; ".join(ruins)


def test_contraste_dos_selos_sobre_fundo_tingido():
    # Selos (tendência, Descontinuada, resultado da coleta, pontos do Por
    # quê) pintam o fundo com a própria cor a 6-14%, inclusive na linha
    # da tabela em hover: o texto deles usa os tons -selo.
    t = _tokens(_css())
    for tx, base in (("--positive-selo", "#22a04a"), ("--danger-selo", "#f85149")):
        for fd in ("--surface", "--surface-hover"):
            tingido = _mistura(base, t[fd], 0.14)
            r = _contraste(t[tx], tingido)
            assert r >= 4.5, f"{tx} sobre {fd} tingido ({tingido}): {r:.2f}:1"


def test_contraste_de_texto_branco_nos_fundos_cheios():
    # Botão de perigo e contador de favoritos: branco por cima.
    t = _tokens(_css())
    for fd in ("--danger-fundo",):
        r = _contraste("#ffffff", t[fd])
        assert r >= 4.5, f"branco sobre {fd} {t[fd]}: {r:.2f}:1"


def test_linhas_escondidas_somem_tambem_no_celular():
    """No celular cada linha da conta vira cartão (display: grid), o que
    passava por cima do atributo `hidden`: busca e filtros não escondiam
    nada lá (achado em 2026-11-16). A regra do `hidden` precisa vir
    depois da regra de cartão."""
    css = (Path(__file__).resolve().parents[1] / "lodout" / "public_site" / "static" / "style.css").read_text(encoding="utf-8")
    cartao = css.index("table.tabela-cards-mobile tbody tr:not(.linha-regras) {")
    escondida = css.rindex("table.tabela-conta tbody tr[hidden] { display: none; }")
    assert escondida > cartao


def test_rotulos_de_venda_por_nao_quebram_no_computador():
    """A rodada 11 da revisão (16/11) pôs `white-space: normal` na linha de
    "Venda por" a partir de 641px e "Sem prejuízo"/"Lucrar 20%" passaram a
    quebrar em todas as linhas a 1280px. Texto maior é tratado com um
    corte em em (empilha rótulo e valor), não com a quebra."""
    css = (Path(__file__).resolve().parents[1] / "lodout" / "public_site" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".tabela-conta .venda-por-linha { white-space: normal; }" not in css
    assert "@media (min-width: 641px) and (max-width: 64em)" in css


def test_superficies_sem_tom_azulado():
    """Fundos ficaram azul-marinho em 19/11 (rgba(18, 24, 38)); o DESIGN.md
    pede cinza neutro. Revisão 20/11: só o botão da Steam pode ser azul."""
    import re as _re
    css = _css()
    assert "rgba(18, 24, 38" not in css
    for cor in ("#0d121c", "#111827"):
        assert cor not in css.lower()
    azuladas = []
    for m in _re.finditer(r"rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)", css):
        r, g, b = map(int, m.groups())
        if b - r >= 12 and b >= g and max(r, g, b) < 60:
            azuladas.append(m.group(0))
    assert not azuladas, azuladas


def test_um_verde_um_vermelho_um_amarelo_sem_cinza_azulado():
    """Revisão 20/11: o CSS tinha 4 verdes, 3 vermelhos e 2 amarelos além
    dos oficiais (--positive, --danger, --warn), e um cinza-azulado
    (#94a3b8) em textos de apoio. Fica um de cada, como no DESIGN.md."""
    css = _css().lower()
    for cor in ("#10b981", "#22c55e", "#34d399", "#4ade80",
                "#ef4444", "#f87171", "#ff8a80", "#facc15", "#94a3b8",
                "rgba(16, 185, 129", "rgba(239, 68, 68", "rgba(148, 163, 184"):
        assert cor not in css, cor


def test_unico_azul_e_o_botao_da_steam():
    """Opção C (pedido do usuário, 20/11): "Mais negociado", "anunciado",
    barrinha de liquidez, faixa "Subiram" e o link "Steam Market" saíram do
    azul-céu. O único azul que fica é o do botão "Entrar com Steam"."""
    import re as _re
    css = _css().lower()
    for cor in ("#38bdf8", "rgba(56, 189, 248", "#0ea5e9", "#0284c7"):
        assert cor not in css, cor
    usos = [m.start() for m in _re.finditer(r"102, 192, 244|#66c0f4", css)]
    for pos in usos:
        inicio = css.rfind("}", 0, pos)
        seletor = css[inicio + 1:css.find("{", inicio)]
        assert ":root" in seletor or "conta-link-entrar" in seletor, seletor.strip()[-80:]
